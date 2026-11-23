import type { AvailabilityStatus, OfferCondition } from "./enums";

export interface SellerRead {
  id: string;
  name: string;
  slug: string;
  website_url: string | null;
  logo_url: string | null;
  is_active: boolean;
}

export interface OfferRead {
  id: string;
  edition_id: string;
  seller: SellerRead;
  external_id: string | null;
  url: string;
  price: string;
  original_price: string | null;
  currency: string;
  condition: OfferCondition;
  availability_status: AvailabilityStatus;
  last_checked_at: string;
}

export interface PriceHistoryRead {
  id: string;
  offer_id: string;
  price: string;
  original_price: string | null;
  availability_status: AvailabilityStatus;
  captured_at: string;
}
