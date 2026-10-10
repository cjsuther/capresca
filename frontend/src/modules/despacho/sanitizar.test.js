import { describe, expect, it } from "vitest";
import { sanitizar } from "./sanitizar";

describe("sanitizar", () => {
  it("conserva el formato del editor", () => {
    const html = '<h2>VISTO</h2><p style="text-align: center;"><b>Art. 1°</b> <i>texto</i></p><ul><li>a</li></ul>';
    expect(sanitizar(html)).toBe(html);
  });

  it("saca scripts, eventos, formularios y enlaces", () => {
    const limpio = sanitizar('<p onclick="x()">a</p><script>alert(1)</script><form><input></form>'
      + '<a href="https://otro.example">link</a><img src="https://otro.example/x.png">');
    expect(limpio).toBe("<p>a</p>link");
  });
});
