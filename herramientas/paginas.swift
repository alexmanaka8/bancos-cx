// Convierte cada página de un PDF (o cada foto) en una imagen JPG reducida.
// Uso: swift paginas.swift carpeta_salida ancho archivo.pdf|foto.jpg [...]
// Las imágenes se numeran 001.jpg, 002.jpg... en el orden recibido.
import PDFKit
import AppKit

let a = CommandLine.arguments
let outDir = a[1], ancho = CGFloat(Double(a[2])!)
var n = 0
func guardar(_ cg: CGImage) {
  n += 1
  let s = min(1, ancho / CGFloat(cg.width))
  let w = Int(CGFloat(cg.width) * s), h = Int(CGFloat(cg.height) * s)
  let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                      space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
  ctx.interpolationQuality = .high
  ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
  let rep = NSBitmapImageRep(cgImage: ctx.makeImage()!)
  let data = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.62])!
  try! data.write(to: URL(fileURLWithPath: outDir + "/" + String(format: "%03d.jpg", n)))
}
for p in a.dropFirst(3) {
  if p.lowercased().hasSuffix(".pdf") {
    let doc = PDFDocument(url: URL(fileURLWithPath: p))!
    for i in 0..<doc.pageCount {
      let page = doc.page(at: i)!
      let box = page.bounds(for: .mediaBox)
      let s = ancho / box.width
      let w = Int(box.width * s), h = Int(box.height * s)
      let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                          space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
      ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
      ctx.scaleBy(x: s, y: s); ctx.translateBy(x: -box.minX, y: -box.minY)
      page.draw(with: .mediaBox, to: ctx)
      guardar(ctx.makeImage()!)
    }
  } else {
    let img = NSImage(contentsOfFile: p)!
    guardar(img.cgImage(forProposedRect: nil, context: nil, hints: nil)!)
  }
}
print(n)
