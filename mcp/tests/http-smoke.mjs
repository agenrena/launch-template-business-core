import assert from "node:assert/strict";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
const { SMOKE_MCP_URL, SMOKE_AGENT_KEY } = process.env;
const client = new Client({ name: "business-core-smoke", version: "1" });
await client.connect(
  new StreamableHTTPClientTransport(new URL(SMOKE_MCP_URL), {
    requestInit: { headers: { Authorization: `Bearer ${SMOKE_AGENT_KEY}` } },
  }),
);
try {
  const { tools } = await client.listTools();
  assert.equal(tools.length, 3);
  const business = await client.callTool({
    name: "get_business",
    arguments: {},
  });
  assert.equal(business.isError, false);
  assert.ok("address" in JSON.parse(business.content[0].text));
  const args = {
    customer_ref: "bcr_5e0ce0000000000000000000000000a1",
    display_name: "Smoke customer",
  };
  const first = await client.callTool({
    name: "update_customer_profile",
    arguments: args,
  });
  const second = await client.callTool({
    name: "update_customer_profile",
    arguments: args,
  });
  assert.deepEqual(
    JSON.parse(first.content[0].text),
    JSON.parse(second.content[0].text),
  );
  const other = await client.callTool({
    name: "get_customer_profile",
    arguments: { customer_ref: "bcr_5e0ce0000000000000000000000000b2" },
  });
  assert.equal(JSON.parse(other.content[0].text).profile, null);
  console.log(
    "Streamable HTTP: initialize, tools/list, scoped read/write and retry passed.",
  );
} finally {
  await client.close();
}
