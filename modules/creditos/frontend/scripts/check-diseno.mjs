#!/usr/bin/env node
// Candado de los Principios de diseño (Controles de Versión → Principios de diseño).
// Reglas duras sobre las PÁGINAS (src/pages/**.tsx):
//   1. «tabla única»  — una <table> cruda debe usar el componente `DataTable` (modelo Maestro de
//      clientes). Excepción: comentario `diseño-ok:` en el archivo, o allowlist diseno-allow-tablas.txt.
//   2. «color por tema» — nada de hex CROMÁTICO fijo (#a1b2c3…): los colores salen de variables de
//      tema (--ok, --warn, --crit, --brand-2, --surface, *-soft…). Se permiten #fff/#000 (house style
//      para texto sobre brand y sombras). Excepción: `diseño-ok:` o allowlist diseno-allow-colores.txt.
//
// Uso:
//   node scripts/check-diseno.mjs                 → escanea todas las páginas
//   node scripts/check-diseno.mjs <archivos...>   → sólo esos archivos (para el hook por-edición)
// Sale con código 1 si hay violaciones (el hook lo traduce a exit 2 = bloquea).
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;        // .../frontend/
const PAGES = join(ROOT, "src/pages");

function cargarAllow(nombre) {
  const p = join(ROOT, "scripts", nombre);
  return new Set(
    existsSync(p)
      ? readFileSync(p, "utf8").split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("#"))
      : []
  );
}
const allowTablas = cargarAllow("diseno-allow-tablas.txt");
const allowColores = cargarAllow("diseno-allow-colores.txt");
const allowClases = cargarAllow("diseno-allow-clases.txt");

// Regla 3 · CSS scopeado por pantalla: una página no puede DEFINIR una clase genérica "bare" (una
// palabra, sin prefijo de scope) en su <style>, porque pisa esa clase en toda la app (bug H-083 del
// calendario). Las clases deben ir prefijadas por pantalla (.fer-…, .pa-…, .tcar-…). Denylist de
// palabras genéricas comunes (layout / componentes) que jamás deben quedar sin scope.
const GENERICAS = new Set(["card","row","col","cols","cell","header","footer","item","items","list",
  "box","grid","title","label","link","active","open","closed","selected","disabled","table","head",
  "body","content","panel","modal","overlay","dialog","wrap","wrapper","inner","outer","bar","dot",
  "tab","tabs","badge","chip","tag","pill","section","main","sidebar","container","btn","button","icon",
  "menu","toolbar","toggle","field","input","form","group","tile","kpi","metric","value","name","status",
  "muted","error","warn","ok","crit","danger","success","info","note","alert","hint","empty"]);
const BARE_RE = /^\.([a-z][a-z0-9]*)$/;   // .foo bare: una clase, una palabra, sin guion ni combinador

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (name.endsWith(".tsx")) out.push(p);
  }
  return out;
}

// Archivos a revisar: los pasados por CLI (si caen dentro de src/pages) o todas las páginas.
const args = process.argv.slice(2).map((a) => (a.startsWith("/") ? a : join(process.cwd(), a)));
const objetivo = args.length
  ? args.filter((a) => a.includes("/src/pages/") && a.endsWith(".tsx") && existsSync(a))
  : walk(PAGES);

const BLANCO_NEGRO = new Set(["#fff", "#ffffff", "#000", "#000000"]);

const violTabla = [];
const violColor = [];
const violScope = [];
const violDialogo = [];
// Diálogos nativos del navegador prohibidos (usar confirmar/avisar/pedirTexto de ui/dialog).
const DIALOGO_RE = /(?:\bwindow\.(?:confirm|alert|prompt)|(?<![.\w])(?:confirm|alert|prompt))\s*\(/;
for (const file of objetivo) {
  const src = readFileSync(file, "utf8");
  const rel = "pages/" + relative(PAGES, file);
  const exento = /dise(ñ|n)o-ok/i.test(src);                 // aclaración explícita en el archivo → exime las reglas

  // Regla 4 · nada de window.confirm/alert/prompt (van los diálogos in-app)
  if (DIALOGO_RE.test(src)) violDialogo.push(rel);

  // Regla 1 · tabla única
  if (/<table[\s>]/.test(src) && !/\bDataTable\b/.test(src) && !exento && !allowTablas.has(rel)) {
    violTabla.push(rel);
  }

  // Regla 2 · color por variable de tema (hex cromático). Ignora los hex que son fallback de una
  // variable (var(--x, #hex)) y el blanco/negro house style.
  const sinFallbacks = src.replace(/var\([^)]*\)/g, "");     // saca los var(--x,#hex) del análisis
  const hex = [...sinFallbacks.matchAll(/#[0-9a-fA-F]{3,8}\b/g)]
    .map((m) => m[0].toLowerCase())
    .filter((h) => !BLANCO_NEGRO.has(h));
  if (hex.length && !exento && !allowColores.has(rel)) {
    violColor.push({ rel, ejemplos: [...new Set(hex)].slice(0, 5) });
  }

  // Regla 3 · CSS scopeado por pantalla: clases genéricas bare definidas en el <style> de la página.
  if (!exento && !allowClases.has(rel)) {
    const genericas = new Set();
    for (const m of src.matchAll(/<style>\{`([\s\S]*?)`\}<\/style>/g)) {
      for (const regla of m[1].matchAll(/([^{}]+)\{[^{}]*\}/g)) {
        for (const sel of regla[1].split(",")) {
          const mm = BARE_RE.exec(sel.trim());
          if (mm && GENERICAS.has(mm[1])) genericas.add(mm[1]);
        }
      }
    }
    if (genericas.size) violScope.push({ rel, clases: [...genericas].slice(0, 6) });
  }
}

let fallo = false;
if (violTabla.length) {
  fallo = true;
  console.error("\n✗ Principio de diseño «tabla única» violado en:");
  for (const v of violTabla) console.error("   · " + v);
  console.error(
    "\n  Las grillas usan el componente DataTable (modelo Maestro de clientes, src/pages/Clientes.tsx).\n" +
    "  Si esta tabla es legítimamente custom, aclará la excepción con un comentario `diseño-ok: <motivo>`\n" +
    "  en el archivo, o sumá su ruta a frontend/scripts/diseno-allow-tablas.txt.\n"
  );
}
if (violColor.length) {
  fallo = true;
  console.error("\n✗ Principio de diseño «color por variable de tema» violado en:");
  for (const v of violColor) console.error(`   · ${v.rel}  (${v.ejemplos.join(", ")})`);
  console.error(
    "\n  Los colores salen de variables de tema (--ok, --warn, --crit, --brand-2, --surface, *-soft…),\n" +
    "  nunca hex cromático fijo (se permiten #fff/#000). Cambiá el hex por la variable semántica, o si es\n" +
    "  una paleta de data-viz legítima, aclará `diseño-ok: <motivo>` o sumá la ruta a\n" +
    "  frontend/scripts/diseno-allow-colores.txt.\n"
  );
}

if (violScope.length) {
  fallo = true;
  console.error("\n✗ Principio de diseño «CSS scopeado por pantalla» violado en:");
  for (const v of violScope) console.error(`   · ${v.rel}  (${v.clases.map((c) => "." + c).join(", ")})`);
  console.error(
    "\n  Una clase genérica sin prefijo (ej. `.card`, `.row`, `.cell`) definida en el <style> de una página\n" +
    "  pisa esa clase en TODA la app (bug H-083 del calendario). Prefijá la clase por pantalla\n" +
    "  (ej. `.fer-cell`, `.pa-row`, `.tcar-dot`), o si es intencional aclará `diseño-ok: <motivo>` /\n" +
    "  sumá la ruta a frontend/scripts/diseno-allow-clases.txt.\n"
  );
}

if (violDialogo.length) {
  fallo = true;
  console.error("\n✗ Principio de diseño «sin diálogos nativos» violado en:");
  for (const v of violDialogo) console.error("   · " + v);
  console.error(
    "\n  No se usan window.confirm/alert/prompt (las cajitas 'localhost says…'). Usá los diálogos in-app\n" +
    "  `confirmar`, `avisar` y `pedirTexto` de src/ui/dialog.tsx.\n"
  );
}

if (fallo) process.exit(1);
console.log(`✓ diseño: ${objetivo.length} página(s) revisada(s) — «tabla única», «color por tema», «CSS scopeado» y «sin diálogos nativos» OK.`);
