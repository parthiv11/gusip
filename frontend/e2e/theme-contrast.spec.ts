import { test, expect, Page } from "@playwright/test";
import { login, Role } from "./fixtures";

/**
 * Regression guard for the class of bug fixed in this session: several
 * components hardcode a "text on dark background" color (e.g. #F2F4F7) that
 * a light-theme CSS shim in index.css remaps for readability — but the shim
 * has to separately list every hardcoded dark background literal those same
 * components use, and components have accumulated many near-duplicate
 * literals (#10151D vs #10151E vs #10141D...) that keep slipping through one
 * at a time. This walks every visible text node and flags any whose color is
 * nearly identical to its effective background, in both themes.
 *
 * Leaflet map internals are excluded: tiles/canvas/SVG overlays defeat a
 * plain DOM background walk and produced one confirmed false positive during
 * manual verification (a perfectly readable label wrongly flagged) — map
 * legibility is covered by the manual screenshots in this session's audit,
 * not by this heuristic.
 */
const PAGES = ["/", "/map", "/cameras", "/alerts", "/search", "/watchlist", "/cases", "/admin"];

interface Finding {
  text: string;
  fg: string;
  bg: string;
  cls: string;
}

function findLowContrastText(): Finding[] {
  function parseColor(c: string) {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const parts = m[1].split(",").map((s) => parseFloat(s.trim()));
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
  }
  function effectiveBg(el: Element | null) {
    // Walk up collecting every (possibly semi-transparent) background layer,
    // then alpha-composite them outermost-first onto an assumed white page
    // base — stopping at the first fully opaque layer needs no base. A
    // naive "first layer with alpha > 0.5 wins" undercounts e.g. a
    // bg-[#10151D]/60 button on a light page, which actually renders as a
    // medium-light blend, not the raw dark color.
    const layers: { r: number; g: number; b: number; a: number }[] = [];
    let node = el;
    while (node) {
      const c = parseColor(getComputedStyle(node).backgroundColor);
      if (c && c.a > 0) layers.push(c);
      if (c && c.a >= 0.999) break;
      node = node.parentElement;
    }
    let result = { r: 255, g: 255, b: 255 };
    for (let i = layers.length - 1; i >= 0; i--) {
      const c = layers[i];
      result = {
        r: c.r * c.a + result.r * (1 - c.a),
        g: c.g * c.a + result.g * (1 - c.a),
        b: c.b * c.a + result.b * (1 - c.a),
      };
    }
    return result;
  }
  function luminance(c: { r: number; g: number; b: number }) {
    return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
  }
  const results: Finding[] = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.textContent || !node.textContent.trim()) return NodeFilter.FILTER_REJECT;
      const el = node.parentElement;
      if (!el || el.closest(".leaflet-container")) return NodeFilter.FILTER_REJECT;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return NodeFilter.FILTER_REJECT;
      const style = getComputedStyle(el);
      if (style.visibility === "hidden" || style.display === "none" || parseFloat(style.opacity) < 0.2) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  let node: Node | null;
  while ((node = walker.nextNode())) {
    const el = node.parentElement!;
    const style = getComputedStyle(el);
    const fg = parseColor(style.color);
    if (!fg) continue;
    const bg = effectiveBg(el);
    const dist = Math.sqrt((fg.r - bg.r) ** 2 + (fg.g - bg.g) ** 2 + (fg.b - bg.b) ** 2);
    const lumDiff = Math.abs(luminance(fg) - luminance(bg));
    if (dist < 30 && lumDiff < 20) {
      results.push({
        text: node.textContent!.trim().slice(0, 60),
        fg: style.color,
        bg: `rgb(${bg.r}, ${bg.g}, ${bg.b})`,
        cls: (el.className || "").toString().slice(0, 100),
      });
    }
  }
  return results;
}

async function auditPage(page: Page, path: string, theme: "light" | "dark") {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await page.evaluate((t) => {
    document.documentElement.dataset.theme = t;
  }, theme);
  await page.waitForTimeout(1000);
  return page.evaluate(findLowContrastText);
}

for (const theme of ["light", "dark"] as const) {
  for (const role of ["operator", "admin"] as Role[]) {
    test(`no near-invisible text in ${theme} mode as ${role}`, async ({ page }) => {
      await login(page, role);
      await page.evaluate((t) => {
        document.documentElement.dataset.theme = t;
        localStorage.setItem("gusip.theme", t);
      }, theme);

      const allFindings: Record<string, Finding[]> = {};
      for (const path of PAGES) {
        const findings = await auditPage(page, path, theme);
        if (findings.length > 0) allFindings[path] = findings;
      }

      expect(allFindings, `Low-contrast text found:\n${JSON.stringify(allFindings, null, 2)}`).toEqual({});
    });
  }
}
