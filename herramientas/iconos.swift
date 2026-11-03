// Dibuja los íconos de la app (se ejecuta una sola vez).
// Uso: swift iconos.swift carpeta_salida
import AppKit

func icono(_ size: Int, _ archivo: String, margen: CGFloat) {
  let s = CGFloat(size)
  let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: size * 4,
                      space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
  // fondo azul clínico a sangre (el sistema recorta las esquinas)
  ctx.setFillColor(CGColor(red: 0x1E/255, green: 0x5F/255, blue: 0xA8/255, alpha: 1))
  ctx.fill(CGRect(x: 0, y: 0, width: s, height: s))
  let area = s * (1 - 2 * margen), o = s * margen
  // tarjeta blanca de pregunta
  let card = CGRect(x: o + area * 0.14, y: o + area * 0.16, width: area * 0.72, height: area * 0.68)
  ctx.setFillColor(CGColor(red: 0.99, green: 0.99, blue: 1, alpha: 1))
  ctx.addPath(CGPath(roundedRect: card, cornerWidth: area * 0.08, cornerHeight: area * 0.08, transform: nil)); ctx.fillPath()
  // tres opciones: la del medio, correcta (ámbar)
  for i in 0..<3 {
    let y = card.maxY - area * (0.2 + CGFloat(i) * 0.17)
    let dot = CGRect(x: card.minX + area * 0.09, y: y - area * 0.045, width: area * 0.09, height: area * 0.09)
    let bar = CGRect(x: dot.maxX + area * 0.05, y: y - area * 0.025, width: area * (i == 1 ? 0.36 : 0.3), height: area * 0.05)
    if i == 1 { ctx.setFillColor(CGColor(red: 0xF2/255, green: 0xB1/255, blue: 0x34/255, alpha: 1)) }
    else { ctx.setFillColor(CGColor(red: 0xC9/255, green: 0xD4/255, blue: 0xE2/255, alpha: 1)) }
    ctx.fillEllipse(in: dot)
    ctx.addPath(CGPath(roundedRect: bar, cornerWidth: bar.height / 2, cornerHeight: bar.height / 2, transform: nil)); ctx.fillPath()
  }
  let rep = NSBitmapImageRep(cgImage: ctx.makeImage()!)
  try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: archivo))
}
let d = CommandLine.arguments[1]
icono(512, d + "/icono-512.png", margen: 0.04)
icono(192, d + "/icono-192.png", margen: 0.04)
icono(512, d + "/icono-maskable-512.png", margen: 0.14)
icono(180, d + "/apple-touch-icon.png", margen: 0.04)
icono(64, d + "/favicon-64.png", margen: 0.02)
