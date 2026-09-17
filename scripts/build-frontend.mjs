import { cp, mkdir, rm } from "node:fs/promises";

// Only public frontend assets belong in the Netlify publish directory.
await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
for (const file of ["index.html", "styles.css", "app.js", "config.js", "assets"]) {
  await cp(file, `dist/${file}`, { recursive: true });
}
