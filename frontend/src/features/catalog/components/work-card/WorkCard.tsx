import type { WorkListItemRead } from "@/types/api";
import styles from "./WorkCard.module.css";

interface WorkCardProps {
  work: WorkListItemRead;
}

const workTypeLabels: Record<WorkListItemRead["work_type"], string> = {
  book: "Livro",
  manga: "Mangá",
  comic: "Quadrinho",
};

export function WorkCard({ work }: WorkCardProps) {
  return (
    <article className={styles.card}>
      <div className={styles.coverPlaceholder} aria-hidden="true">
        <span className={styles.placeholderMark} />
      </div>
      <div className={styles.content}>
        <span className={styles.type}>{workTypeLabels[work.work_type]}</span>
        <h2 className={styles.title}>{work.title}</h2>
        {work.subtitle && <p className={styles.subtitle}>{work.subtitle}</p>}
        {work.original_language && (
          <p className={styles.language}>
            Idioma original: {work.original_language}
          </p>
        )}
      </div>
    </article>
  );
}
