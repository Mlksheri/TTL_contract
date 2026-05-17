import { Devnet } from "starknet-devnet";

const devnet = await Devnet.spawnVersion("v0.6.1", {
  args: ["--host", "127.0.0.1", "--port", "5050", "--seed", "0"],
});

console.log(`Starknet Devnet running at ${devnet.url}`);
console.log("Press Ctrl+C to stop.");

process.on("SIGINT", async () => {
  await devnet.stop();
  process.exit(0);
});

await new Promise(() => {});
