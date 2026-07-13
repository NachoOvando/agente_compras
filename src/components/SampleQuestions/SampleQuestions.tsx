interface SampleQuestionsProps {
  questions: string[];
  disabled: boolean;
  onSelect: (question: string) => void;
}

export default function SampleQuestions({
  questions,
  disabled,
  onSelect,
}: SampleQuestionsProps) {
  return (
    <div>
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Preguntas de ejemplo
      </h2>
      <div className="flex flex-wrap gap-2">
        {questions.map((q) => (
          <button
            key={q}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(q)}
            className="cursor-pointer rounded-full border border-border bg-card px-3 py-1.5 text-xs text-secondary transition-colors duration-200 hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
