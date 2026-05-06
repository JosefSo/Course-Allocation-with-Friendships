#sourceLocation(file: "-e", line: 1)
import Foundation; import PDFKit; let url = URL(fileURLWithPath: "/Users/josefsokolov/Downloads/Course Allocation.pdf"); guard let doc = PDFDocument(url: url) else { print("NO"); exit(0) }; print("PAGES=\(doc.pageCount)"); for i in 0..<doc.pageCount { if let page = doc.page(at: i), let s = page.string { print("---PAGE \(i+1)---"); print(s) } }
