import { request } from "@/lib/api/client";
import type {
  GoogleBooksImportRequest,
  GoogleBooksImportResponse,
} from "@/types/api";

export function importGoogleBooks(
  body: GoogleBooksImportRequest,
): Promise<GoogleBooksImportResponse> {
  return request("/catalog/imports/google-books", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
