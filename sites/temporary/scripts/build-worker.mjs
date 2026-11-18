import fs from "node:fs/promises";
import path from "node:path";
import { build } from "esbuild";
const files = await fs.readdir("build/client/assets");
const assets = {};
for (const file of files) {
  const type = file.endsWith(".css")
    ? "text/css; charset=utf-8"
    : file.endsWith(".js")
      ? "text/javascript; charset=utf-8"
      : null;
  if (!type) throw new Error("Unrecognized static asset");
  assets["/static/ui/assets/" + file] = {
    body: await fs.readFile(path.join("build/client/assets", file), "utf8"),
    type,
  };
}
await fs.writeFile("build/assets.json", JSON.stringify(assets));
await fs.mkdir("dist/server", { recursive: true });
await fs.mkdir("dist/.openai", { recursive: true });
await build({
  entryPoints: ["worker/index.js"],
  outfile: "dist/server/index.js",
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  minify: true,
});
await fs.copyFile(".openai/hosting.json", "dist/.openai/hosting.json");
await fs.cp("drizzle", "dist/.openai/drizzle", { recursive: true });
console.log(
  "Built self-contained Sites Worker with local static assets and D1 schema migrations.",
);
