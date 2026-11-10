// Face boxes for every image in a folder, as JSON lines: name x y w h (0..1, top-left origin)
import Foundation
import Vision
import AppKit
let dir = CommandLine.arguments[1]
let files = try! FileManager.default.contentsOfDirectory(atPath: dir).filter { $0.hasSuffix(".jpg") }.sorted()
for f in files {
    guard let img = NSImage(contentsOfFile: dir + "/" + f),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    let faces = (req.results ?? []).sorted { $0.boundingBox.width > $1.boundingBox.width }
    if let b = faces.first?.boundingBox {
        print("\(f) \(b.minX) \(1 - b.maxY) \(b.width) \(b.height)")
    } else { print("\(f) none") }
}
