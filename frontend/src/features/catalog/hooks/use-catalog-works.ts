"use client";

import { useCallback, useEffect, useState } from "react";
import { HttpError } from "@/lib/api/client";
import { listWorks } from "@/services/api/catalog";
import type {
  PaginatedResponse,
  WorkListItemRead,
  WorkType,
} from "@/types/api";

const PAGE_SIZE = 20;

interface CatalogQueryState {
  key: string;
  response: PaginatedResponse<WorkListItemRead> | null;
  error: string | null;
}

export function useCatalogWorks() {
  const [page, setPage] = useState(1);
  const [selectedType, setSelectedType] = useState<WorkType | "">("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [queryState, setQueryState] = useState<CatalogQueryState>({
    key: "",
    response: null,
    error: null,
  });
  const queryKey = JSON.stringify([appliedSearch, selectedType, page, reloadKey]);

  useEffect(() => {
    let active = true;

    void listWorks({
      q: appliedSearch || undefined,
      work_type: selectedType || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((result) => {
        if (active) {
          setQueryState({ key: queryKey, response: result, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!active) return;

        const message =
          error instanceof HttpError
            ? error.message
            : "Não foi possível carregar o catálogo. Tente novamente.";

        setQueryState({ key: queryKey, response: null, error: message });
      });

    return () => {
      active = false;
    };
  }, [appliedSearch, page, queryKey, reloadKey, selectedType]);

  const applyFilters = useCallback((search: string, type: WorkType | "") => {
    setAppliedSearch(search.trim());
    setSelectedType(type);
    setPage(1);
    setReloadKey((key) => key + 1);
  }, []);

  const goToPage = useCallback(
    (nextPage: number) => {
      const totalPages =
        (queryState.key === queryKey ? queryState.response?.total_pages : 0) ?? 0;
      if (nextPage < 1 || nextPage > totalPages || nextPage === page) return;
      setPage(nextPage);
    },
    [page, queryKey, queryState.key, queryState.response?.total_pages],
  );

  const retry = useCallback(() => {
    setReloadKey((key) => key + 1);
  }, []);

  return {
    works:
      queryState.key === queryKey ? queryState.response?.items ?? [] : [],
    pagination: queryState.key === queryKey ? queryState.response : null,
    page,
    selectedType,
    appliedSearch,
    isLoading: queryState.key !== queryKey,
    error: queryState.key === queryKey ? queryState.error : null,
    applyFilters,
    goToPage,
    retry,
  };
}
