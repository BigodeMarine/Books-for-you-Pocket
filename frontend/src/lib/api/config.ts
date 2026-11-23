const missingApiBaseUrlMessage =
  "NEXT_PUBLIC_API_BASE_URL is not configured. Set it to the API base URL, for example http://localhost:8000/api/v1.";

export function getApiBaseUrl(): string {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

  if (!configuredBaseUrl) {
    throw new Error(missingApiBaseUrlMessage);
  }

  return configuredBaseUrl.replace(/\/+$/, "");
}
