/**
 * TagChip — renders a filter_tags entry as a clickable chip.
 *
 * Three states: default, hover (CSS), active (is-active class).
 * Click navigates to filtered view via ?tag= URL param.
 */

import { useNavigate, useSearchParams } from 'react-router-dom';

interface TagChipProps {
  tag: string;
  runId: string;
}

export function TagChip({ tag, runId }: TagChipProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const activeTag = searchParams.get('tag');
  const isActive = activeTag === tag;

  function handleClick(e: React.MouseEvent) {
    e.preventDefault();
    if (isActive) {
      navigate(`/runs/${runId}/brief`);
    } else {
      navigate(`/runs/${runId}/brief?tag=${encodeURIComponent(tag)}`);
    }
  }

  return (
    <span
      className={`tag-chip${isActive ? ' is-active' : ''}`}
      onClick={handleClick}
      role="button"
      tabIndex={0}
    >
      {tag}
    </span>
  );
}
