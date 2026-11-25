"use client";

import { useState, type FormEvent } from "react";
import type { WorkType } from "@/types/api";
import { useCatalogWorks } from "../../hooks/use-catalog-works";
import { WorkCard } from "../work-card/WorkCard";
import styles from "./CatalogListing.module.css";

function parseWorkType(value: string): WorkType | "" {
  if (value === "book" || value === "manga" || value === "comic") {
    return value;
  }

  return "";
}

export function CatalogListing() {
  const catalog = useCatalogWorks();
  const [searchDraft, setSearchDraft] = useState(catalog.appliedSearch);
  const [typeDraft, setTypeDraft] = useState<WorkType | "">(
    catalog.selectedType,
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    catalog.applyFilters(searchDraft, typeDraft);
  }

  const totalPages = catalog.pagination?.total_pages ?? 0;
  const currentPage = totalPages === 0 ? 0 : catalog.pagination?.page ?? 0;
  const hasFilters = Boolean(catalog.appliedSearch || catalog.selectedType);

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.header}>
          <p className={styles.eyebrow}>BOOKS FOR YOUR POCKET</p>
          <h1 className={styles.heading}>Descubra sua próxima leitura</h1>
          <p className={styles.intro}>
            Explore livros, mangás e quadrinhos para encontrar sua próxima
            história.
          </p>
        </header>

        <form className={styles.filters} onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label htmlFor="catalog-search">Buscar por título</label>
            <input
              id="catalog-search"
              name="q"
              type="search"
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
              placeholder="Ex.: O caminho dos reis"
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="catalog-work-type">Tipo de obra</label>
            <select
              id="catalog-work-type"
              name="work_type"
              value={typeDraft}
              onChange={(event) => setTypeDraft(parseWorkType(event.target.value))}
            >
              <option value="">Todos os tipos</option>
              <option value="book">Livro</option>
              <option value="manga">Mangá</option>
              <option value="comic">Quadrinho</option>
            </select>
          </div>
          <button className={styles.submitButton} type="submit">
            <span aria-hidden="true">⌕</span>
            <span>Buscar obras</span>
          </button>
        </form>

        <section className={styles.results} aria-labelledby="results-heading">
          <div className={styles.resultsHeader}>
            <div>
              <h2 id="results-heading">Catálogo</h2>
              {!catalog.isLoading && !catalog.error && catalog.pagination && (
                <p className={styles.resultCount}>
                  {catalog.pagination.total === 1
                    ? "1 obra encontrada"
                    : `${catalog.pagination.total} obras encontradas`}
                </p>
              )}
            </div>
          </div>

          {catalog.isLoading && (
            <div className={styles.state} role="status" aria-live="polite">
              <span className={styles.spinner} aria-hidden="true" />
              <p>Carregando obras do catálogo…</p>
            </div>
          )}

          {!catalog.isLoading && catalog.error && (
            <div className={styles.errorState} role="alert">
              <p>{catalog.error}</p>
              <button
                className={styles.secondaryButton}
                type="button"
                onClick={catalog.retry}
              >
                Tentar novamente
              </button>
            </div>
          )}

          {!catalog.isLoading && !catalog.error && catalog.pagination && (
            <>
              {catalog.works.length > 0 ? (
                <div className={styles.grid}>
                  {catalog.works.map((work) => (
                    <WorkCard key={work.id} work={work} />
                  ))}
                </div>
              ) : (
                <div className={styles.emptyState}>
                  <h3>
                    {hasFilters
                      ? "Nenhuma obra corresponde à sua busca"
                      : "O catálogo ainda está vazio"}
                  </h3>
                  <p>
                    {hasFilters
                      ? "Tente outro título ou ajuste o tipo de obra."
                      : "Novas obras aparecerão aqui quando forem cadastradas."}
                  </p>
                </div>
              )}

              {totalPages > 1 && (
                <nav className={styles.pagination} aria-label="Paginação do catálogo">
                  <button
                    className={styles.pageButton}
                    type="button"
                    onClick={() => catalog.goToPage(currentPage - 1)}
                    disabled={currentPage <= 1}
                    aria-label="Ir para a página anterior"
                  >
                    Anterior
                  </button>
                  <p aria-live="polite">
                    Página {currentPage} de {totalPages}
                  </p>
                  <button
                    className={styles.pageButton}
                    type="button"
                    onClick={() => catalog.goToPage(currentPage + 1)}
                    disabled={currentPage === 0 || currentPage >= totalPages}
                    aria-label="Ir para a próxima página"
                  >
                    Próxima
                  </button>
                </nav>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
