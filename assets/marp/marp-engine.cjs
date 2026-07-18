const { createRequire } = require("node:module");

const requireFromCli = createRequire(process.argv[1] || __filename);
const marpCore = requireFromCli("@marp-team/marp-core");
const Marp = marpCore.Marp || marpCore.default || marpCore;

module.exports = class MaryMarp extends Marp {
  constructor(options = {}) {
    const mathOptions = typeof options.math === "object" ? options.math : {};
    const emojiOptions = typeof options.emoji === "object" ? options.emoji : {};
    super({
      ...options,
      emoji: {
        shortcode: false,
        unicode: false,
        ...emojiOptions,
      },
      math: {
        lib: "katex",
        katexFontPath: "../fonts/katex/",
        ...mathOptions,
      },
    });
  }
};
