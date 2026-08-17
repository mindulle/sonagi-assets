import fs from "fs";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";

async function main() {
    const query = process.argv[2];
    const limit = parseInt(process.argv[3], 10);

    const authData = JSON.parse(
        fs.readFileSync("/home/ubuntu/.local/share/opencode/mcp-auth.json", "utf8"),
    );
    const mobbinToken = authData.mobbin.tokens.accessToken;

    const transport = new SSEClientTransport(new URL("https://api.mobbin.com/mcp"), {
        requestInit: {
            headers: {
                Authorization: `Bearer ${mobbinToken}`,
            },
        },
    });

    const client = new Client(
        { name: "opencode-analysis", version: "1.0.0" },
        { capabilities: {} },
    );

    await client.connect(transport);

    try {
        const result = await client.callTool({
            name: "mobbin_search_screens",
            arguments: {
                query: query,
                platform: "ios",
                limit: limit,
                mode: "standard",
                image_format: "webp",
            },
        });
        console.log(JSON.stringify(result));
    } catch (err) {
        console.error(err);
    } finally {
        process.exit(0);
    }
}

main().catch(console.error);
