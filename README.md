# Flatcap for FreshRSS

![Version](https://img.shields.io/badge/version-2.0.0-blueviolet) ![FreshRSS](https://img.shields.io/badge/FreshRSS-1.30-blue) ![License](https://img.shields.io/badge/license-MIT-blue)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/screenshot-slate.png">
    <source media="(prefers-color-scheme: light)" srcset="images/screenshot-daylight.png">
    <img src="images/screenshot-slate.png" alt="FreshRSS with Flatcap: categorized sidebar with unread counts and the current feed highlighted, next to an article list with thumbnails and summaries" width="100%">
  </picture>
</p>

<p align="center"><sub>Slate or Daylight is shown to match your GitHub appearance.</sub></p>

**Flatcap for FreshRSS** brings the Flatcap visual system to your feed reader: matte graphite surfaces, one mineral-blue accent, IBM Plex for the interface and the reading column, Cascadia for code.

> The interface organizes. Content takes the foreground. Color informs.

It is a single stylesheet for FreshRSS's **User CSS** extension, built on top of the **Nord** theme. Two independently tuned modes are included, **Slate** (dark) and **Daylight** (light), plus a version that follows your operating system.

## Quiet precision

[Flatcap](https://github.com/cheycron/flat-cap-theme) is a semantic visual system for focused work. Colors are named for **what they do**, not for how they look, and the two modes share roles rather than identical values: Daylight is not an inverted Slate.

- **Hierarchy before decoration.** Spacing, alignment and type organize the reader; surfaces stay neutral and matte.
- **Useful color.** Mineral blue marks interaction; feedback colors appear only for real states, always with words.
- **Explicit interaction.** Focus, selection, unread and current are distinct signals that do not depend on color alone.
- **Content first.** The article column gets IBM Plex at a comfortable measure; code gets Cascadia with restrained syntax colors.

## What is in the box

| File                   | Use it when                                                     |
|:---------------------- |:--------------------------------------------------------------- |
| `flatcap.css`          | You want **Slate**, always dark.                                |
| `flatcap-daylight.css` | You want **Daylight**, always light.                            |
| `flatcap-system.css`   | You want Slate or Daylight to follow the OS light/dark setting. |

All three share the same rules. They differ only in which color tokens they define.

## Install

1. **Choose the base theme.** In FreshRSS, open **Configuration → Display** and set **Theme** to **Nord**. Flatcap re-colors Nord's structure, so this step is required.
2. **Enable the extension.** Open **Configuration → Extensions** and enable **User CSS**.
3. **Open its settings.** Click the extension's name (or its gear) to open the settings page. It has a single text area.
4. **Paste the stylesheet.** Copy the full contents of one of the three files above, paste it into the text area, and press **Submit**.
5. **Reload FreshRSS.** The theme applies on the next page load.

To switch modes later, replace the pasted text with another file. To go back, empty the text area.

> **Fonts.** After step 5 the interface works, but IBM Plex and Cascadia will only appear if FreshRSS is allowed to load them. See the next section.

## Fonts and the Content Security Policy

The stylesheet starts with an `@import` of IBM Plex Sans, Cascadia Code and Cascadia Mono from Google Fonts.

**FreshRSS blocks it by default.** Out of the box FreshRSS sends a Content Security Policy of `default-src 'self'`. That also governs styles and fonts, so the browser refuses the Google Fonts stylesheet and the font files it points to. Nothing breaks: the font stacks include fallbacks (Segoe UI, `system-ui`, `ui-monospace`, Consolas), and the layout and colors are unaffected. You simply see system fonts instead of Plex and Cascadia.

Pick one of these:

**Option A: install the fonts locally (recommended).** Nothing to change in FreshRSS, and no third-party requests. Install **IBM Plex Sans**, **Cascadia Code** and **Cascadia Mono** on the devices you read on. The stylesheet names them as local families, so they are used as soon as they exist. The blocked `@import` is harmless; you may delete that line from your pasted copy.

**Option B: allow Google Fonts in your CSP.** If you control the web server or reverse proxy in front of FreshRSS, extend the policy it sends so that:

- `style-src` includes `'self'` and `https://fonts.googleapis.com`
- `font-src` includes `'self'` and `https://fonts.gstatic.com`

Keep the rest of your policy unchanged. This makes every browser request fonts from Google, so prefer Option A if privacy matters to you. How to set the header depends on your deployment (Apache, nginx, Caddy, a container image); this repository does not change it for you.

## Compatibility

- **FreshRSS 1.30**, with the **Nord** base theme and the **User CSS** extension (tested with 1.30.0 and User CSS 1.1.2).
- Other FreshRSS versions or base themes may work, but they are not tested. Flatcap styles Nord's markup, so a different base theme will not look right.
- Rendering was checked in Chromium. Other browsers are not tested.

## Accessibility and preferences

- **Contrast.** Text, borders, focus rings, alerts and syntax colors were measured in the running interface in both modes. The ratios met their targets, for example body text above 7:1 and secondary text above 5:1.
- **Increased contrast.** `prefers-contrast: more` switches to stronger text and border colors.
- **Focus.** A 2px ring with a 2px offset on every focusable control.
- **Not by color alone.** The current feed or article carries an accent edge and a heavier weight. Alerts keep FreshRSS's own labels.
- **Reduced motion.** Transitions are disabled when the OS asks for it.
- **Forced colors.** Active states keep an outline, and icons and favicons stay visible.
- **Touch.** Controls grow to a 44px target on coarse pointers.

## How it is built

The files are generated; do not edit them by hand.

- `src/theme.json` holds the Flatcap 2.0 values: colors, type and metrics. It is a copy of the core.
- `src/rules.css` holds the FreshRSS rules. They are written against Flatcap roles and never use raw colors.
- `scripts/build.py` combines them into the three stylesheets. It needs Python 3.10+ and nothing else.

```sh
python3 scripts/build.py            # regenerate the three .css files
python3 scripts/build.py --check    # fail if the .css files are out of date
python3 scripts/build.py --sync     # refresh src/theme.json from ../00-Flatcap, then rebuild
python3 scripts/build.py --contrast # print token-level contrast ratios
```

`--sync` expects the core checkout next to this repository (`../00-Flatcap`); pass a path to use another one. Icon colors are fitted to the role colors with a deterministic solver, so the same input always yields the same output.

Colors come from [Flatcap](https://github.com/cheycron/flat-cap-theme), the core of the system.

## License

MIT. Fonts are not bundled and carry their own licenses.

## Support

If Flatcap makes your reading calmer, you can support its development.

<p align="center">
  <a href="https://www.buymeacoffee.com/cheycron">
    <img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me a Coffee">
  </a>
</p>
