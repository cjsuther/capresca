import DOMPurify from "dompurify";

/**
 * El cuerpo de los instrumentos es HTML que escriben los usuarios, viene de los modelos o se importó de
 * los DBF del sistema anterior: antes de mostrarlo se deja sólo el formato del editor (sin scripts,
 * formularios, enlaces ni imágenes externas).
 */
const OPCIONES = {
  ALLOWED_TAGS: ["p", "br", "div", "span", "b", "strong", "i", "em", "u", "s", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "blockquote", "table", "thead", "tbody", "tr", "th", "td", "font", "center"],
  ALLOWED_ATTR: ["style", "align", "class", "colspan", "rowspan"],
};

export const sanitizar = (html) => DOMPurify.sanitize(html || "", OPCIONES);
