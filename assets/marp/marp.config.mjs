import path from "node:path";
import { fileURLToPath } from "node:url";

const assetRoot = path.dirname(fileURLToPath(import.meta.url));

export default {
  allowLocalFiles: true,
  engine: path.join(assetRoot, "marp-engine.cjs"),
  themeSet: [path.join(assetRoot, "themes", "mary-shanghaitech-red.css")],
};
