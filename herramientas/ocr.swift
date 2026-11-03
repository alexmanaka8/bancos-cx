// Reconoce el texto de fotos o PDF escaneados con el OCR de macOS (Vision), sin internet.
// Uso: swift ocr.swift salida.json archivo.pdf          (cada página)
//      swift ocr.swift salida.json foto1.jpg foto2.jpg  (cada foto es una "página")
// Devuelve líneas con posición y fracción de resaltado, igual que extraer_pdf.swift.
import Vision
import PDFKit
import AppKit

let args = CommandLine.arguments
var images: [CGImage] = []
if args[2].lowercased().hasSuffix(".pdf") {
  let doc = PDFDocument(url: URL(fileURLWithPath: args[2]))!
  for i in 0..<doc.pageCount {
    let page = doc.page(at: i)!
    let box = page.bounds(for: .mediaBox)
    let s: CGFloat = 1600 / max(box.width, box.height)
    let w = Int(box.width * s), h = Int(box.height * s)
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                        space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: s, y: s); ctx.translateBy(x: -box.minX, y: -box.minY)
    page.draw(with: .mediaBox, to: ctx)
    images.append(ctx.makeImage()!)
  }
} else {
  for p in args.dropFirst(2) {
    let img = NSImage(contentsOfFile: p)!
    images.append(img.cgImage(forProposedRect: nil, context: nil, hints: nil)!)
  }
}

var out: [[String: Any]] = []
for (pi, cg) in images.enumerated() {
  let W = cg.width, H = cg.height
  let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: W * 4,
                      space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
  ctx.draw(cg, in: CGRect(x: 0, y: 0, width: W, height: H))
  let px = ctx.data!.bindMemory(to: UInt8.self, capacity: W * H * 4)
  let req = VNRecognizeTextRequest()
  req.recognitionLevel = .accurate
  req.recognitionLanguages = ["es-ES", "en-US"]
  req.usesLanguageCorrection = true
  try! VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
  let k = 800.0 / Double(max(W, H))  // unidades ~ puntos de una hoja
  for obs in req.results ?? [] {
    guard let c = obs.topCandidates(1).first else { continue }
    let b = obs.boundingBox  // normalizado, origen abajo-izquierda
    let x0 = Int(b.minX * CGFloat(W)), x1 = Int(b.maxX * CGFloat(W))
    let yTop = Int((1 - b.maxY) * CGFloat(H)), yBot = Int((1 - b.minY) * CGFloat(H))
    var hl = 0, tot = 0
    for y in stride(from: max(0, yTop), to: min(H, yBot), by: 2) {
      for x in stride(from: max(0, x0), to: min(W, x1), by: 2) {
        let i = (y * W + x) * 4
        let r = Int(px[i]), g = Int(px[i + 1]), bl = Int(px[i + 2])
        let mx = max(r, g, bl), mn = min(r, g, bl)
        tot += 1
        if mx > 170 && mx - mn > 70 && !(r > 150 && g < 120 && bl < 120) { hl += 1 }
      }
    }
    out.append(["p": pi + 1, "t": c.string, "x": Double(x0) * k, "y": Double(yTop) * k,
                "w": Double(x1 - x0) * k, "h": Double(yBot - yTop) * k,
                "hl": tot > 0 ? Double(hl) / Double(tot) : 0, "ocr": true])
  }
}
let data = try! JSONSerialization.data(withJSONObject: ["pages": images.count, "lines": out])
try! data.write(to: URL(fileURLWithPath: args[1]))
print("\(images.count) páginas, \(out.count) líneas")
