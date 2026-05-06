#sourceLocation(file: "-e", line: 1)
import Foundation; import PDFKit; let url = URL(fileURLWithPath: "/Users/josefsokolov/Downloads/ORSIS_2022_Satellites.pdf"); if let doc = PDFDocument(url: url) { print(doc.pageCount); for i in 0..<doc.pageCount { if let page = doc.page(at: i), let s = page.string { print("---PAGE---"); print(s) } } } else { print("NO") }
