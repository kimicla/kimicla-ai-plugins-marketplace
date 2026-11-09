import AppKit
import Foundation

// Explicitly read a screenshot or image from the macOS clipboard.
// The image bytes go to stdout for a LOCAL process only, never to Claude Code.
let board = NSPasteboard.general
let validExtensions: Set<String> = ["png", "jpg", "jpeg", "heic", "tiff", "tif", "webp"]
let limitBytes = 25 * 1024 * 1024

func die(_ reason: String) -> Never {
    fputs("local-ocr clipboard: \(reason)\n", stderr)
    exit(2)
}

func getImage() -> NSImage? {
    // If Finder copied a file, prefer the original image, not its thumbnail.
    if let objects = board.readObjects(forClasses: [NSURL.self],
                                       options: [.urlReadingFileURLsOnly: true]) {
        for obj in objects {
            guard let url = obj as? URL,
                  url.isFileURL,
                  validExtensions.contains(url.pathExtension.lowercased()) else {
                continue
            }
            if let image = NSImage(contentsOf: url) { return image }
        }
    }
    for type in [NSPasteboard.PasteboardType.png, NSPasteboard.PasteboardType.tiff] {
        guard let data = board.data(forType: type),
              data.count <= limitBytes else { continue }
        if let image = NSImage(data: data) { return image }
    }
    return nil
}

guard let image = getImage() else {
    die("No supported image in the clipboard. Copy a screenshot or image first.")
}
guard let tiff = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      bitmap.pixelsWide > 0, bitmap.pixelsHigh > 0,
      Double(bitmap.pixelsWide) * Double(bitmap.pixelsHigh) <= 16_000_000,
      let png = bitmap.representation(using: .png, properties: [:]),
      png.count <= limitBytes else {
    die("Could not decode clipboard image or it exceeds the 16MP/25MB limit.")
}
FileHandle.standardOutput.write(png)
