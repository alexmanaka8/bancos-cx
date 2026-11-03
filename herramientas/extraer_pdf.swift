// Extrae las líneas de texto de un PDF con su posición y si están resaltadas.
// Uso: swift extraer_pdf.swift archivo.pdf salida.json
// Detecta columnas (huecos verticales sin tinta) y lee cada columna por separado.
import PDFKit
import AppKit

let args = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: args[1]))!
let S: CGFloat = 2  // escala de renderizado

struct Bmp { let w: Int; let h: Int; let data: UnsafeMutablePointer<UInt8> }

func render(_ page: PDFPage, _ box: CGRect) -> Bmp {
  let w = Int(box.width * S), h = Int(box.height * S)
  let cs = CGColorSpaceCreateDeviceRGB()
  let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                      space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
  ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
  ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
  ctx.scaleBy(x: S, y: S)
  ctx.translateBy(x: -box.minX, y: -box.minY)
  page.draw(with: .mediaBox, to: ctx)
  return Bmp(w: w, h: h, data: ctx.data!.bindMemory(to: UInt8.self, capacity: w * h * 4))
}

// píxel en coordenadas de página (origen abajo-izquierda)
@inline(__always) func px(_ b: Bmp, _ x: Int, _ y: Int) -> (Int, Int, Int) {
  let row = b.h - 1 - y
  let i = (row * b.w + x) * 4
  return (Int(b.data[i]), Int(b.data[i + 1]), Int(b.data[i + 2]))
}
@inline(__always) func isInk(_ c: (Int, Int, Int)) -> Bool { (c.0 + c.1 + c.2) < 380 }
@inline(__always) func isHighlight(_ c: (Int, Int, Int)) -> Bool {
  let mx = max(c.0, c.1, c.2), mn = min(c.0, c.1, c.2)
  return mx > 170 && mx - mn > 70 && !(c.0 > 150 && c.1 < 120 && c.2 < 120)  // color vivo, no rojo de tinta
}

// Bloques de lectura: franjas horizontales separadas por espacio en blanco,
// y dentro de cada franja, columnas separadas por huecos verticales sin tinta.
// Columnas de una franja horizontal (filas y0...y1 del dibujo): huecos verticales sin tinta.
func columnas(_ b: Bmp, _ box: CGRect, _ y0: Int, _ y1: Int) -> [CGRect] {
  let top = box.minY + CGFloat(y1 + 1) / S, bot = box.minY + CGFloat(y0) / S
  let full = CGRect(x: box.minX, y: bot - 1, width: box.width, height: top - bot + 2)
  if CGFloat(y1 - y0) / S < 30 { return [full] }
  var colInk = [Int](repeating: 0, count: b.w); var rows = 0
  for yy in stride(from: y0, through: y1, by: 2) {
    var any = false
    for x in 0..<b.w where isInk(px(b, x, yy)) { colInk[x] += 1; any = true }
    if any { rows += 1 }
  }
  guard let first = colInk.firstIndex(where: { $0 > 0 }), let last = colInk.lastIndex(where: { $0 > 0 }) else { return [full] }
  var cuts: [CGFloat] = []; var runStart = -1
  let minRun = Int(6 * S), lim = max(1, rows * 6 / 100)
  for x in first...last {
    if colInk[x] <= lim { if runStart < 0 { runStart = x } }
    else {
      if runStart >= 0 && x - runStart >= minRun {
        let mid = CGFloat(runStart + x) / 2 / S + box.minX
        let rel = (mid - box.minX) / box.width
        if rel > 0.2 && rel < 0.8 { cuts.append(mid) }
      }
      runStart = -1
    }
  }
  var edges = [box.minX] + cuts + [box.maxX]
  edges = edges.reduce(into: [CGFloat]()) { if let l = $0.last, $1 - l < 40 { return }; $0.append($1) }
  edges[edges.count - 1] = box.maxX
  return (0..<(edges.count - 1)).map { CGRect(x: edges[$0], y: full.minY, width: edges[$0 + 1] - edges[$0], height: full.height) }
}

// Bloques de lectura. Si toda la página tiene columnas (texto a 2 o 3 columnas), se lee columna por columna.
// Si no (páginas mixtas: recuadros arriba y texto a lo ancho abajo), se parte en franjas horizontales
// separadas por espacio en blanco y cada franja se lee por columnas.
func blocks(_ b: Bmp, _ box: CGRect) -> [CGRect] {
  var rowHas = [Bool](repeating: false, count: b.h)
  for y in 0..<b.h { var x = 0; while x < b.w { if isInk(px(b, x, y)) { rowHas[y] = true; break }; x += 2 } }
  guard let yMin = rowHas.firstIndex(of: true), let yMax = rowHas.lastIndex(of: true) else { return [] }
  let pagina = columnas(b, box, yMin, yMax)
  if pagina.count > 1 { return pagina }
  var bands: [(Int, Int)] = []
  var y = 0
  let gap = Int(8 * S)
  while y < b.h {
    if !rowHas[y] { y += 1; continue }
    var end = y, blank = 0, k = y
    while k < b.h { if rowHas[k] { end = k; blank = 0 } else { blank += 1; if blank >= gap { break } }; k += 1 }
    bands.append((y, end)); y = end + 1
  }
  return bands.reversed().flatMap { columnas(b, box, $0.0, $0.1) }   // de arriba hacia abajo
}

var out: [[String: Any]] = []
for pi in 0..<doc.pageCount {
  guard let page = doc.page(at: pi) else { continue }
  let box = page.bounds(for: .mediaBox)
  let b = render(page, box)
  for (ci, r) in blocks(b, box).enumerated() {
    guard let sel = page.selection(for: r) else { continue }
    for line in sel.selectionsByLine() {
      let t = (line.string ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
      if t.isEmpty { continue }
      let lb = line.bounds(for: page).intersection(r)
      if lb.isNull || lb.width < 1 { continue }
      var hl = 0, tot = 0
      let x0 = max(0, Int((lb.minX - box.minX) * S)), x1 = min(b.w - 1, Int((lb.maxX - box.minX) * S))
      let y0 = max(0, Int((lb.minY - box.minY) * S)), y1 = min(b.h - 1, Int((lb.maxY - box.minY) * S))
      if x1 > x0 && y1 > y0 {
        for y in stride(from: y0, through: y1, by: 2) { for x in stride(from: x0, through: x1, by: 2) {
          tot += 1; if isHighlight(px(b, x, y)) { hl += 1 } } }
      }
      out.append(["p": pi + 1, "c": ci, "t": t,
                  "x": Double(lb.minX - box.minX), "y": Double(box.maxY - lb.maxY),
                  "w": Double(lb.width), "h": Double(lb.height),
                  "hl": tot > 0 ? Double(hl) / Double(tot) : 0])
    }
  }
}
let data = try! JSONSerialization.data(withJSONObject: ["pages": doc.pageCount, "lines": out])
try! data.write(to: URL(fileURLWithPath: args[2]))
print("\(doc.pageCount) páginas, \(out.count) líneas")
