(() => {
  const RESULT_ID = "mary-image-overflow-audit-result";

  const nextFrame = () => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  });

  const rectObject = (rect) => ({
    left: rect.left,
    right: rect.right,
    top: rect.top,
    bottom: rect.bottom,
    width: rect.width,
    height: rect.height,
  });

  const publish = (payload) => {
    const serialized = JSON.stringify(payload);
    document.open();
    document.write(`<!doctype html><html><body><pre id="${RESULT_ID}"></pre></body></html>`);
    document.close();
    document.getElementById(RESULT_ID).textContent = serialized;
  };

  const run = async () => {
    try {
      if (document.fonts && document.fonts.ready) {
        await Promise.race([
          document.fonts.ready,
          new Promise((resolve) => setTimeout(resolve, 2000)),
        ]);
      }
      const slides = Array.from(document.querySelectorAll("section"));
      const images = slides.flatMap((slide) => Array.from(slide.querySelectorAll("img")));
      await Promise.race([
        Promise.all(images.map((image) => image.decode().catch(() => undefined))),
        new Promise((resolve) => setTimeout(resolve, 2000)),
      ]);

      const slideSvgs = Array.from(document.querySelectorAll("svg[data-marpit-svg]"));
      const originalClasses = slideSvgs.map((svg) => svg.getAttribute("class") || "");
      const originalStyles = slideSvgs.map((svg) => svg.getAttribute("style"));
      const records = [];

      for (let index = 0; index < slides.length; index += 1) {
        const slide = slides[index];
        const slideSvg = slide.closest("svg[data-marpit-svg]");
        for (const svg of slideSvgs) {
          Object.assign(svg.style, {
            position: "fixed",
            left: "0",
            top: "0",
            width: "1280px",
            height: "720px",
            visibility: "hidden",
          });
          svg.style.contentVisibility = "hidden";
          svg.style.opacity = "0";
        }
        if (slideSvg) {
          slideSvg.style.visibility = "visible";
          slideSvg.style.contentVisibility = "visible";
          slideSvg.style.opacity = "1";
        }
        await nextFrame();

        const slideRect = slide.getBoundingClientRect();
        for (const image of slide.querySelectorAll("img")) {
          records.push({
            page: index + 1,
            src: image.getAttribute("src") || "",
            loaded: image.complete && image.naturalWidth > 0 && image.naturalHeight > 0,
            natural_width: image.naturalWidth,
            natural_height: image.naturalHeight,
            slide_rect: rectObject(slideRect),
            image_rect: rectObject(image.getBoundingClientRect()),
          });
        }
      }

      slideSvgs.forEach((svg, index) => {
        svg.setAttribute("class", originalClasses[index]);
        if (originalStyles[index] === null) svg.removeAttribute("style");
        else svg.setAttribute("style", originalStyles[index]);
      });
      publish({ total_slides: slides.length, records });
    } catch (error) {
      publish({ error: error instanceof Error ? error.message : String(error) });
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => setTimeout(run, 0), { once: true });
  } else setTimeout(run, 0);
})();
