import type { EditionFormat, WorkType } from "./enums";

export interface ExistingWorkTarget {
  kind: "existing";
  work_id: string;
}

export interface NewWorkTarget {
  kind: "new";
  work_type: WorkType;
}

export type WorkTarget = ExistingWorkTarget | NewWorkTarget;

export interface GoogleBooksImportRequest {
  provider_id: string;
  work_target: WorkTarget;
  edition_format?: EditionFormat | null;
  language_fallback?: string | null;
}

export type GoogleBooksImportWarningCode =
  | "isbn_invalid"
  | "isbn_already_assigned"
  | "publication_date_incomplete"
  | "publication_date_invalid"
  | "author_ambiguous"
  | "genre_ambiguous"
  | "genre_slug_collision";

export interface GoogleBooksImportWarning {
  code: GoogleBooksImportWarningCode;
  message: string;
}

export interface GoogleBooksImportResponse {
  work_id: string;
  edition_id: string;
  work_created: boolean;
  edition_created: boolean;
  warnings: GoogleBooksImportWarning[];
}
