// Uso: libros_texto [--ocr] libro.pdf salida.jsonl
// Escribe una línea JSON por página: {"p": n, "t": "texto"}.
// Con --ocr (o si la página casi no tiene texto) lee la página con Vision.
import Foundation
import PDFKit
import Vision
import AppKit

var args = Array(CommandLine.arguments.dropFirst())
let forzarOCR = args.first == "--ocr"
if forzarOCR { args.removeFirst() }
// --desde N: continuar un archivo a medias (se agregan las páginas desde la N)
var desde = 1
if args.first == "--desde" { desde = Int(args[1]) ?? 1; args.removeFirst(2) }
guard args.count == 2, let doc = PDFDocument(url: URL(fileURLWithPath: args[0])) else {
    FileHandle.standardError.write("uso: libros_texto [--ocr] libro.pdf salida.jsonl\n".data(using: .utf8)!); exit(1)
}
if desde == 1 || !FileManager.default.fileExists(atPath: args[1]) { FileManager.default.createFile(atPath: args[1], contents: nil) }
let out = FileHandle(forWritingAtPath: args[1])!
out.seekToEndOfFile()

func ocr(_ page: PDFPage) -> String {
    let box = page.bounds(for: .mediaBox)
    let esc = 3600 / max(box.width, 1)   // alta resolución: hay libros que son capturas con letra chica
    let img = page.thumbnail(of: NSSize(width: box.width * esc, height: box.height * esc), for: .mediaBox)
    guard let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { return "" }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["es-ES", "en-US"]
    try? VNImageRequestHandler(cgImage: cg).perform([req])
    // orden de lectura aproximado: por columnas (franjas de 1/8 del ancho) y de arriba hacia abajo
    let obs = (req.results ?? []).sorted { (Int($0.boundingBox.minX * 8), -$0.boundingBox.maxY) < (Int($1.boundingBox.minX * 8), -$1.boundingBox.maxY) }
    return obs.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

for i in (desde - 1)..<doc.pageCount {
    autoreleasepool {
        guard let page = doc.page(at: i) else { return }
        var t = forzarOCR ? "" : (page.string ?? "")
        if t.count < 80 { t = ocr(page) }
        let linea = try! JSONSerialization.data(withJSONObject: ["p": i + 1, "t": t])
        out.write(linea); out.write("\n".data(using: .utf8)!)
    }
}
