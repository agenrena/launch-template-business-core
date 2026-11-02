"""The store on Agenrena: this App is its Vendor and the store grants it once.
The platform is faked at the HTTP layer."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import OperationalError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core import services
from core.agenrena import AgenrenaError, _json
from core.models import AgenrenaConnection, AuditEvent, Business, CustomerIdentity, Membership
from core.permissions import human_actor
from core.services import deliver_to_customer, notify_customer, update_business

from .test_core import PASSWORD, ref

A = ref(0xA)
CHAT_URL = "https://agenrena.example/s/i/Ab12Cd34/chat"
GRANT = {
    "grant_id": "grant-A",
    "business_name": "大安店",
    "chat_url": CHAT_URL,
    "scopes": ["messages:send"],
}
VENDOR = {"AGENRENA_VENDOR_ID": "vendor-1", "AGENRENA_VENDOR_SECRET": "bvs_private_vendor_secret"}
CARD = {
    "status": "success",
    "header": "店家已接單",
    "content": [{"label": "取餐號", "value": "12"}],
}


class FakeAgenrena:
    """Just enough of the Business Integration API, recording each call."""

    def __init__(self):
        self.calls = []
        self.tokens = 0
        self.session = {"status": "pending"}
        self.reject_token_once = False
        self.send_error = None
        self.grants = []

    def __call__(self, method, path, body=None, *, token="", grant_id=""):
        self.calls.append({"method": method, "path": path, "body": body, "grant_id": grant_id})
        if path == "/api/business-api/token/":
            self.tokens += 1
            return 200, {
                "access_token": f"bit_{self.tokens}",
                "expires_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            }
        if self.reject_token_once and token == "bit_1":
            self.reject_token_once = False
            return 401, {"error": {"code": "INTEGRATION_TOKEN_INVALID"}}
        if path == "/api/business-api/authorize/start/":
            return 201, {
                "session_id": str(uuid.uuid4()),
                "authorize_url": "https://agenrena.com/business/authorize/?token=bct_once",
                "expires_at": (timezone.now() + timedelta(minutes=5)).isoformat(),
            }
        if path.startswith("/api/business-api/authorize/session/"):
            return 200, self.session
        if path == "/api/business-api/grants/" and method == "GET":
            return 200, self.grants
        if path.startswith("/api/business-api/grants/"):
            return 204, {}
        if path == "/api/business-api/messages/send/":
            if self.send_error:
                return self.send_error
            return 200, {"id": "message"}
        return 404, {"error": {"code": "NOT_FOUND"}}

    def completed(self, grant_id="grant-A", name="大安店", chat_url=CHAT_URL):
        self.session = {
            "status": "completed",
            "grant_id": grant_id,
            "business_name": name,
            "chat_url": chat_url,
        }

    def paths(self, method=None):
        return [c["path"] for c in self.calls if method in (None, c["method"])]


@override_settings(**VENDOR)
class AgenrenaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="owner", password=PASSWORD)
        Membership.objects.create(user=cls.owner, role="owner")
        cls.admin = User.objects.create_user(username="manager", password=PASSWORD)
        Membership.objects.create(user=cls.admin, role="admin")

    def setUp(self):
        cache.clear()
        self.platform = FakeAgenrena()
        patcher = patch("core.agenrena._request", self.platform)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.owner_client = APIClient()
        self.owner_client.force_login(self.owner)
        self.admin_client = APIClient()
        self.admin_client.force_login(self.admin)

    def post(self, action, client=None):
        return (client or self.owner_client).post(
            f"/api/console/agenrena/{action}/", {}, format="json"
        )

    def connect(self, **completed):
        start = self.post("connect")
        self.assertEqual(start.status_code, 201, start.data)
        self.platform.completed(**completed)
        return self.post("check")

    def overview(self, client=None):
        return (client or self.owner_client).get("/api/console/agenrena/").json()

    def test_store_connects_its_business_profile(self):
        self.assertIsNone(self.overview()["chat_url"])
        start = self.post("connect")
        self.assertEqual(start.status_code, 201)
        self.assertEqual(start["Cache-Control"], "no-store")
        self.assertIn("authorize_url", start.data)
        self.assertEqual(self.platform.calls[-1]["body"], {"scopes": ["messages:send"]})
        self.assertEqual(self.post("check").data["status"], "pending")
        self.assertEqual(AgenrenaConnection.current().chat_url, "")
        self.assertIsNone(self.overview()["chat_url"])
        self.platform.completed()
        done = self.post("check")
        self.assertEqual(done.data["status"], "connected")
        self.assertEqual(done.data["business_name"], "大安店")
        self.assertEqual(done.data["chat_url"], CHAT_URL)
        self.assertEqual(AgenrenaConnection.current().chat_url, CHAT_URL)
        overview = self.overview()
        self.assertTrue(overview["configured"])
        self.assertEqual(overview["status"], "connected")
        self.assertEqual(overview["business_name"], "大安店")
        self.assertEqual(overview["chat_url"], CHAT_URL)
        self.assertEqual(self.overview(self.admin_client)["chat_url"], CHAT_URL)
        # The consent link is a bearer credential: never stored or audited.
        self.assertNotIn("bct_once", str(list(AgenrenaConnection.objects.values())))
        self.assertNotIn("bct_once", str(list(AuditEvent.objects.values())))
        self.assertTrue(AuditEvent.objects.filter(action="agenrena.connected").exists())

    def test_completed_consent_requires_a_valid_chat_url(self):
        self.post("connect")
        session_id = AgenrenaConnection.current().session_id
        for value in [
            None,
            "",
            123,
            {},
            "/s/i/Ab12Cd34/chat",
            "javascript:alert(1)",
            "ftp://agenrena.example/chat",
            "https://agenrena.example/" + "x" * 2048,
        ]:
            with self.subTest(chat_url=value):
                self.platform.completed(chat_url=value)
                response = self.post("check")
                self.assertEqual(response.status_code, 502)
                self.assertIn("INVALID_CONSENT_RESPONSE", response.data["details"])
                connection = AgenrenaConnection.current()
                self.assertEqual(connection.status, "pending")
                self.assertEqual(connection.session_id, session_id)
                self.assertEqual(connection.grant_id, "")
                self.assertEqual(connection.chat_url, "")
                self.assertFalse(AuditEvent.objects.filter(action="agenrena.connected").exists())
        self.platform.completed()
        del self.platform.session["chat_url"]
        self.assertEqual(self.post("check").status_code, 502)
        self.assertEqual(AgenrenaConnection.current().status, "pending")
        # A corrected upstream response can complete the same pending session.
        self.platform.completed(chat_url="http://localhost:8020/s/i/Ab12Cd34/chat")
        response = self.post("check")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["chat_url"], self.platform.session["chat_url"])

    def test_expired_consent_returns_to_unconnected(self):
        self.post("connect")
        self.platform.session = {"status": "expired"}
        self.assertEqual(self.post("check").data, {"status": "expired", "chat_url": None})
        self.assertIsNone(AgenrenaConnection.current())

    def test_connected_store_must_disconnect_before_reconnecting(self):
        self.connect()
        self.assertEqual(self.post("connect").status_code, 409)

    def test_disconnect_hands_the_grant_back(self):
        self.connect()
        response = self.post("disconnect")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "none", "chat_url": None})
        self.assertIsNone(self.overview()["chat_url"])
        self.assertEqual(self.platform.paths("DELETE"), ["/api/business-api/grants/grant-A/"])
        self.assertIsNone(AgenrenaConnection.current())
        self.assertTrue(AuditEvent.objects.filter(action="agenrena.disconnected").exists())

    def test_admin_reads_status_but_only_owner_manages(self):
        self.assertEqual(self.admin_client.get("/api/console/agenrena/").status_code, 200)
        for action in ["connect", "check", "sync", "disconnect"]:
            self.assertEqual(self.post(action, self.admin_client).status_code, 403)
        self.assertEqual(self.platform.calls, [])

    @override_settings(AGENRENA_VENDOR_ID="", AGENRENA_VENDOR_SECRET="")
    def test_unconfigured_deployment_keeps_working_without_agenrena(self):
        self.assertEqual(self.overview(), {"configured": False, "status": "none", "chat_url": None})
        self.assertEqual(self.post("connect").status_code, 400)
        self.assertEqual(self.post("sync").status_code, 400)
        identity = CustomerIdentity.objects.create(agenrena_customer_ref=A)
        self.assertFalse(deliver_to_customer(identity, "訂單已送出"))
        self.assertEqual(self.platform.calls, [])

    def test_platform_outage_is_reported_without_secrets(self):
        def down(*args, **kwargs):
            from core.agenrena import AgenrenaError

            raise AgenrenaError("UNAVAILABLE")

        with patch("core.agenrena._request", down):
            result = self.post("connect")
        self.assertEqual(result.status_code, 502)
        self.assertNotIn("bvs_private_vendor_secret", str(result.data))
        self.assertIsNone(AgenrenaConnection.current())

    def test_manual_check_imports_existing_grant_without_consent(self):
        # The HTTP decoder must preserve the list returned by Agenrena.
        self.platform.grants = _json(json.dumps([GRANT]).encode())
        response = self.post("sync")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "connected")
        self.assertEqual(response.data["chat_url"], CHAT_URL)
        connection = AgenrenaConnection.current()
        self.assertEqual(connection.grant_id, "grant-A")
        self.assertEqual(connection.business_name, "大安店")
        self.assertEqual(connection.connected_by, self.owner)
        self.assertIsNone(connection.session_id)
        self.assertEqual(
            self.platform.paths(),
            [
                "/api/business-api/token/",
                "/api/business-api/grants/",
            ],
        )
        event = AuditEvent.objects.get(action="agenrena.connection_checked")
        self.assertEqual(event.actor_id, str(self.owner.pk))
        self.assertEqual(event.detail, {})
        self.assertEqual(self.overview(self.admin_client)["chat_url"], CHAT_URL)
        # Repeat checks retain the original local connection timestamp.
        self.assertEqual(self.post("sync").status_code, 200)
        self.assertEqual(AgenrenaConnection.objects.count(), 1)
        self.assertEqual(AgenrenaConnection.current().connected_at, connection.connected_at)

    def test_manual_check_no_grants_allows_explicit_consent(self):
        self.assertEqual(self.post("sync").data, {"status": "none", "chat_url": None})
        self.assertIsNone(AgenrenaConnection.current())
        self.assertNotIn("/api/business-api/authorize/start/", self.platform.paths())
        self.assertEqual(self.connect().data["status"], "connected")
        # A successful empty response clears a stale local grant and chat URL.
        self.assertEqual(self.post("sync").data, {"status": "none", "chat_url": None})
        self.assertIsNone(AgenrenaConnection.current())
        self.assertEqual(self.platform.paths("DELETE"), [])

    def test_manual_check_replaces_pending_consent(self):
        self.post("connect")
        self.platform.grants = [GRANT]
        self.assertEqual(self.post("sync").status_code, 200)
        connection = AgenrenaConnection.current()
        self.assertEqual(connection.status, "connected")
        self.assertIsNone(connection.session_id)
        self.assertIsNone(connection.session_expires_at)
        self.assertEqual(self.post("check").data["chat_url"], CHAT_URL)

    def test_manual_check_errors_preserve_existing_connection(self):
        self.connect()
        before = AgenrenaConnection.objects.values().get()
        for payload, status in [
            (_json(b"<html>Unavailable</html>"), 502),
            (None, 502),
            ([GRANT, {**GRANT, "grant_id": "grant-B"}], 409),
            ([{}], 502),
            ([{**GRANT, "grant_id": ""}], 502),
            ([{**GRANT, "business_name": None}], 502),
            ([{**GRANT, "chat_url": "javascript:alert(1)"}], 502),
            ([{**GRANT, "scopes": "messages:send"}], 502),
            ([{**GRANT, "scopes": []}], 409),
        ]:
            with self.subTest(payload=payload):
                self.platform.grants = payload
                response = self.post("sync")
                self.assertEqual(response.status_code, status, response.data)
                self.assertEqual(AgenrenaConnection.objects.values().get(), before)
        with patch("core.agenrena._request", side_effect=AgenrenaError("UNAVAILABLE")):
            self.assertEqual(self.post("sync").status_code, 502)
        self.assertEqual(AgenrenaConnection.objects.values().get(), before)
        self.assertFalse(AuditEvent.objects.filter(action="agenrena.connection_checked").exists())

    def test_manual_check_does_not_overwrite_a_concurrent_change(self):
        self.connect()
        self.platform.grants = [GRANT]

        def platform_with_change(method, path, *args, **kwargs):
            if path == "/api/business-api/grants/":
                AgenrenaConnection.objects.filter(pk=1).update(
                    status="revoked",
                    updated_at=timezone.now(),
                )
            return self.platform(method, path, *args, **kwargs)

        with patch("core.agenrena._request", side_effect=platform_with_change):
            self.assertEqual(self.post("sync").status_code, 409)
        self.assertEqual(AgenrenaConnection.current().status, "revoked")

    def test_manual_check_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(self.post("sync", client).status_code, 403)
        self.assertEqual(self.platform.calls, [])

    def test_notification_is_sent_after_commit(self):
        self.connect()
        identity = CustomerIdentity.objects.create(agenrena_customer_ref=A)
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            notify_customer(identity, "店家已接單 · 取餐號 12", card=CARD, message_id="order-1")
        # Nothing is sent before the business write commits.
        self.assertNotIn("/api/business-api/messages/send/", self.platform.paths())
        for callback in callbacks:
            callback()
        sent = self.platform.calls[-1]
        self.assertEqual(sent["path"], "/api/business-api/messages/send/")
        self.assertEqual(sent["grant_id"], "grant-A")
        self.assertEqual(
            sent["body"],
            {
                "customer_ref": A,
                "text": "店家已接單 · 取餐號 12",
                "card": CARD,
                "client_message_id": "order-1",
            },
        )
        event = AuditEvent.objects.get(action="agenrena.message_sent")
        self.assertEqual(event.customer, identity)
        self.assertEqual(event.actor_type, "system")
        self.assertNotIn("取餐號", str(event.detail))

    def test_customer_without_reference_or_connection_is_skipped(self):
        manual = CustomerIdentity.objects.create(display_name="Walk-in")
        unconnected = CustomerIdentity.objects.create(agenrena_customer_ref=A)
        with self.captureOnCommitCallbacks(execute=True):
            notify_customer(manual, "x")
            notify_customer(unconnected, "x")
            notify_customer(None, "x")
        self.assertEqual(self.platform.calls, [])

    def test_store_revoking_the_app_stops_delivery(self):
        self.connect()
        identity = CustomerIdentity.objects.create(agenrena_customer_ref=A)
        self.platform.send_error = (403, {"error": {"code": "INTEGRATION_GRANT_REVOKED"}})
        self.assertFalse(deliver_to_customer(identity, "x"))
        self.assertEqual(AgenrenaConnection.current().status, "revoked")
        self.assertEqual(
            AuditEvent.objects.get(action="agenrena.message_failed").detail,
            {"error": "INTEGRATION_GRANT_REVOKED"},
        )
        sends = len(self.platform.paths("POST"))
        self.assertFalse(deliver_to_customer(identity, "x"))
        self.assertEqual(len(self.platform.paths("POST")), sends)
        self.assertEqual(self.overview()["status"], "revoked")
        self.assertIsNone(self.overview()["chat_url"])
        self.assertIsNone(self.post("check").data["chat_url"])
        # Reconnecting starts a fresh authorization.
        self.assertEqual(self.post("connect").status_code, 201)
        self.assertEqual(AgenrenaConnection.current().chat_url, "")
        self.assertIsNone(self.overview()["chat_url"])
        next_url = "https://stage.agenrena.example/s/i/NewStore/chat"
        self.platform.completed(grant_id="grant-B", chat_url=next_url)
        done = self.post("check")
        self.assertEqual(done.data["status"], "connected")
        self.assertEqual(done.data["chat_url"], next_url)
        self.assertEqual(AgenrenaConnection.current().chat_url, next_url)

    def test_unknown_customer_is_a_failed_delivery_not_an_error(self):
        self.connect()
        identity = CustomerIdentity.objects.create(agenrena_customer_ref=A)
        self.platform.send_error = (
            400,
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "fields": {"customer_ref": [{"code": "CUSTOMER_NOT_FOUND"}]},
                }
            },
        )
        self.assertFalse(deliver_to_customer(identity, "x"))
        self.assertEqual(AgenrenaConnection.current().status, "connected")
        self.assertEqual(
            AuditEvent.objects.get(action="agenrena.message_failed").detail,
            {"error": "CUSTOMER_NOT_FOUND"},
        )

    def test_vendor_token_is_cached_and_refreshed_once_when_rejected(self):
        self.connect()
        self.assertEqual(self.platform.tokens, 1)
        identity = CustomerIdentity.objects.create(agenrena_customer_ref=A)
        self.platform.reject_token_once = True
        self.assertTrue(deliver_to_customer(identity, "x"))
        self.assertEqual(self.platform.tokens, 2)
        token_calls = [c for c in self.platform.calls if c["path"].endswith("/token/")]
        self.assertEqual(token_calls[0]["body"]["vendor_id"], "vendor-1")
        self.assertNotIn(
            "bvs_private_vendor_secret",
            str(list(AuditEvent.objects.values())) + str(self.overview()),
        )


@override_settings(**VENDOR)
class ConnectionConcurrencyTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.platform = FakeAgenrena()
        self.platform.grants = [GRANT]
        patcher = patch("core.agenrena._request", self.platform)
        patcher.start()
        self.addCleanup(patcher.stop)
        Business.current()
        owner = get_user_model().objects.create_user(username="owner")
        Membership.objects.create(user=owner, role="owner")
        self.actor = human_actor(owner)
        self.identity = CustomerIdentity.objects.create(agenrena_customer_ref=A)
        AgenrenaConnection.objects.create(
            status="connected", grant_id=GRANT["grant_id"], chat_url=CHAT_URL
        )

    def sync_with_concurrent_write(self, write):
        save = services._save_agenrena_connection
        concurrent = None

        def run_write():
            close_old_connections()
            try:
                return write()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=1) as pool:

            def save_with_concurrent_write(*args, **kwargs):
                nonlocal concurrent
                # Sync has checked its revision but has not saved yet. Allow the
                # other request to finish if the connection row is not locked.
                concurrent = pool.submit(run_write)
                try:
                    concurrent.result(timeout=2)
                except FutureTimeout:
                    # A locked writer resumes after sync commits below.
                    pass
                return save(*args, **kwargs)

            with patch(
                "core.services._save_agenrena_connection",
                side_effect=save_with_concurrent_write,
            ):
                result = services.sync_agenrena_connection(self.actor)
                self.assertEqual(result["status"], "connected")
            concurrent.result(timeout=10)

    def test_sync_does_not_resurrect_a_concurrently_disconnected_grant(self):
        self.sync_with_concurrent_write(lambda: services.disconnect_agenrena(self.actor))
        self.assertIsNone(AgenrenaConnection.current())
        self.assertTrue(AuditEvent.objects.filter(action="agenrena.disconnected").exists())

    def test_sync_does_not_overwrite_a_concurrent_delivery_revocation(self):
        self.platform.send_error = (403, {"error": {"code": "INTEGRATION_GRANT_REVOKED"}})
        self.sync_with_concurrent_write(lambda: deliver_to_customer(self.identity, "test"))
        self.assertEqual(AgenrenaConnection.current().status, "revoked")
        self.assertTrue(AuditEvent.objects.filter(action="agenrena.message_failed").exists())


@override_settings(**VENDOR)
class NotificationCommitTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.platform = FakeAgenrena()
        patcher = patch("core.agenrena._request", self.platform)
        patcher.start()
        self.addCleanup(patcher.stop)
        Business.current()
        owner = get_user_model().objects.create_user(username="owner")
        Membership.objects.create(user=owner, role="owner")
        self.actor = human_actor(owner)
        self.identity = CustomerIdentity.objects.create(agenrena_customer_ref=A)
        AgenrenaConnection.objects.create(status="connected", grant_id="grant-A", chat_url=CHAT_URL)

    def commit_notification(self, failure=None):
        following_callback = Mock()
        with ExitStack() as stack:
            with transaction.atomic():
                update_business(self.actor, {"name": "Committed store"})
                # Faults apply to delivery, after the business write and its audit.
                if failure is not None:
                    stack.enter_context(failure)
                notify_customer(self.identity, "private message", card=CARD)
                transaction.on_commit(following_callback)
                self.assertNotIn("/api/business-api/messages/send/", self.platform.paths())
        self.assertEqual(Business.current().name, "Committed store")
        self.assertTrue(AuditEvent.objects.filter(action="business.updated").exists())
        following_callback.assert_called_once_with()

    def test_notification_runs_after_real_commit(self):
        self.commit_notification()
        self.assertIn("/api/business-api/messages/send/", self.platform.paths())
        self.assertTrue(AuditEvent.objects.filter(action="agenrena.message_sent").exists())

    def test_platform_failure_preserves_committed_write(self):
        self.commit_notification(
            patch("core.agenrena._request", side_effect=AgenrenaError("UNAVAILABLE"))
        )
        event = AuditEvent.objects.get(action="agenrena.message_failed")
        self.assertEqual(event.detail, {"error": "UNAVAILABLE"})

    def test_unexpected_delivery_failures_are_isolated_and_redacted(self):
        for target, error in [
            ("core.agenrena._request", ValueError("private message bvs_private_vendor_secret")),
            (
                "core.services.AgenrenaConnection.objects.filter",
                OperationalError("private query values"),
            ),
        ]:
            with self.subTest(target=target):
                AuditEvent.objects.filter(action="agenrena.message_failed").delete()
                self.commit_notification(patch(target, side_effect=error))
                event = AuditEvent.objects.get(action="agenrena.message_failed")
                self.assertEqual(event.detail, {"error": "DELIVERY_OUTCOME_UNKNOWN"})

    def test_audit_failure_is_isolated_for_successful_and_failed_delivery(self):
        for platform_error in [None, (503, {"error": {"code": "UNAVAILABLE"}})]:
            with self.subTest(platform_error=platform_error):
                self.platform.calls.clear()
                self.platform.send_error = platform_error
                with self.assertLogs("core.services", level="ERROR") as logs:
                    self.commit_notification(
                        patch(
                            "core.services.AuditEvent.objects.create",
                            side_effect=OperationalError(
                                "private message bvs_private_vendor_secret"
                            ),
                        )
                    )
                self.assertEqual(
                    logs.output,
                    ["ERROR:core.services:Agenrena delivery outcome could not be recorded."],
                )
                self.assertTrue(all(record.exc_info is None for record in logs.records))
                self.assertEqual(self.platform.paths().count("/api/business-api/messages/send/"), 1)

    def test_rollback_discards_notification_and_business_audit(self):
        original_name = Business.current().name
        with self.assertRaisesMessage(ValueError, "rollback"):
            with transaction.atomic():
                update_business(self.actor, {"name": "Rolled back store"})
                notify_customer(self.identity, "private message")
                raise ValueError("rollback")
        self.assertEqual(Business.current().name, original_name)
        self.assertFalse(AuditEvent.objects.exists())
        self.assertEqual(self.platform.calls, [])
