export interface ExternalBookRead {
  provider_id: string;
  title: string;
  authors: string[];
  publisher: string | null;
  published_date: string | null;
  description: string | null;
  isbn_10: string | null;
  isbn_13: string | null;
  page_count: number | null;
  categories: string[];
  language: string | null;
  thumbnail_url: string | null;
  info_link: string | null;
  preview_link: string | null;
}
