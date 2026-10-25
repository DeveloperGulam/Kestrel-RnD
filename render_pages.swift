
import Foundation
import PDFKit
import AppKit

let args = CommandLine.arguments
if args.count > 1 {
    let url = URL(fileURLWithPath: args[1])
    if let doc = PDFDocument(url: url) {
        print("PDF pages: \(doc.pageCount)")
        for i in 0..<doc.pageCount {
            if let page = doc.page(at: i) {
                let rect = page.bounds(for: .mediaBox)
                let image = NSImage(size: rect.size)
                image.lockFocus()
                if let context = NSGraphicsContext.current?.cgContext {
                    context.setFillColor(NSColor.white.cgColor)
                    context.fill(rect)
                    page.draw(with: .mediaBox, to: context)
                }
                image.unlockFocus()
                if let tiff = image.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff), let png = rep.representation(using: .png, properties: [:]) {
                    let outPath = "\(args[1])_page_\(i+1).png"
                    try? png.write(to: URL(fileURLWithPath: outPath))
                    print("Wrote \(outPath)")
                }
            }
        }
    }
}
