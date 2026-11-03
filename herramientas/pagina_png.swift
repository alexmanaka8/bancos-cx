// Uso: pagina_png archivo.pdf N salida.png [ancho]
// Dibuja una página del PDF como imagen, para comparar el texto extraído con el original.
import Foundation
import PDFKit
import AppKit

let a = CommandLine.arguments
guard a.count >= 4, let doc = PDFDocument(url: URL(fileURLWithPath: a[1])),
      let n = Int(a[2]), let page = doc.page(at: n - 1) else {
    FileHandle.standardError.write("uso: pagina_png archivo.pdf N salida.png [ancho]\n".data(using: .utf8)!); exit(1)
}
let ancho = a.count > 4 ? CGFloat(Double(a[4]) ?? 1400) : 1400
let box = page.bounds(for: .mediaBox)
let img = page.thumbnail(of: NSSize(width: ancho, height: box.height * ancho / box.width), for: .mediaBox)
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: a[3]))
