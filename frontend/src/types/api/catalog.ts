import type { EditionFormat, MetadataSource, WorkType } from "./enums";

export interface AuthorRead {
  id: string;
  name: string;
}

export interface GenreRead {
  id: string;
  name: string;
  slug: string;
}

export interface EditionRead {
  id: string;
  work_id: string;
  isbn_10: string | null;
  isbn_13: string | null;
  publisher: string | null;
  language: string;
  format: EditionFormat;
  volume_number: number | null;
  publication_date: string | null;
  page_count: number | null;
  cover_url: string | null;
  metadata_source: MetadataSource | null;
  metadata_external_id: string | null;
  metadata_updated_at: string | null;
}

export interface WorkListItemRead {
  id: string;
  title: string;
  subtitle: string | null;
  work_type: WorkType;
  original_language: string | null;
}

export interface WorkDetailRead extends WorkListItemRead {
  description: string | null;
  created_at: string;
  updated_at: string;
  editions: EditionRead[];
  authors: AuthorRead[];
  genres: GenreRead[];
}
