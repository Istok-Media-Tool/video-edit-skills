// Faces and hands in still frames, with Apple Vision (used by check_caption_overlap.py).
// Usage: vision_look a.png b.png ...   (paths, or read from stdin when none given)
// Output, one line per image: path [F x y w h]... [H x y w h]...   (pixels, top-left origin)
import Vision
import AppKit

func look(_ p: String) {
  guard let img = NSImage(contentsOfFile: p),
        let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print(p); return }
  let fr = VNDetectFaceRectanglesRequest()
  let hr = VNDetectHumanHandPoseRequest(); hr.maximumHandCount = 4
  try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([fr, hr])
  let W = Double(cg.width), H = Double(cg.height)
  var out = p
  for f in fr.results ?? [] { let b = f.boundingBox
    out += " F \(Int(b.minX*W)) \(Int((1-b.maxY)*H)) \(Int(b.width*W)) \(Int(b.height*H))" }
  for h in hr.results ?? [] {
    guard let pts = try? h.recognizedPoints(.all) else { continue }
    let ok = pts.values.filter { $0.confidence > 0.3 }
    if ok.count < 6 { continue }
    let xs = ok.map { $0.location.x }, ys = ok.map { $0.location.y }
    let x0 = xs.min()!, x1 = xs.max()!, y0 = ys.min()!, y1 = ys.max()!
    out += " H \(Int(x0*W)) \(Int((1-y1)*H)) \(Int((x1-x0)*W)) \(Int((y1-y0)*H))"
  }
  print(out)
}
var paths = Array(CommandLine.arguments.dropFirst())
if paths.isEmpty { while let l = readLine() { if !l.isEmpty { paths.append(l) } } }
for p in paths { autoreleasepool { look(p) } }
