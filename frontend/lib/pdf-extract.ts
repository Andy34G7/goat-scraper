import * as pdfjsLib from 'pdfjs-dist';

// Ensure worker is set up correctly for client-side usage
if (typeof window !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;
}

export async function extractTextFromPdfUrl(url: string): Promise<string> {
    try {
        const loadingTask = pdfjsLib.getDocument(url);
        const pdf = await loadingTask.promise;

        let fullText = '';
        const numPages = pdf.numPages;

        // Extract text from the first 50 pages maximum (to prevent hanging on massive pdfs)
        const maxPages = Math.min(numPages, 50);

        for (let i = 1; i <= maxPages; i++) {
            const page = await pdf.getPage(i);
            const textContent = await page.getTextContent();
            const pageText = textContent.items
                .map((item: any) => item.str)
                .join(' ');

            fullText += pageText + '\n\n';
        }

        if (numPages > maxPages) {
            fullText += `\n\n[Note: Document truncated to first ${maxPages} pages due to size limits.]`;
        }

        return fullText;
    } catch (error) {
        console.error("Failed to extract PDF text:", error);
        throw new Error("Could not read PDF contents");
    }
}

export async function extractTextFromFile(file: File): Promise<string> {
    if (file.type === 'application/pdf') {
        const arrayBuffer = await file.arrayBuffer();
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        const pdf = await loadingTask.promise;

        let fullText = '';
        const maxPages = Math.min(pdf.numPages, 50);

        for (let i = 1; i <= maxPages; i++) {
            const page = await pdf.getPage(i);
            const textContent = await page.getTextContent();
            const pageText = textContent.items
                .map((item: any) => item.str)
                .join(' ');

            fullText += pageText + '\n\n';
        }
        return fullText;
    } else {
        // Assume text-based file (txt, md, csv, etc)
        return await file.text();
    }
}
