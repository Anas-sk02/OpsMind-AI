import React from 'react';
import type { OrderStatus } from '../../types';

interface StatusBadgeProps {
  status: OrderStatus | string;
  type?: 'order' | 'task' | 'stock' | 'email';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  let label = status.replace(/_/g, ' ');
  let colorStyle: { bg: string; text: string; border: string; dot: string } = {
    bg: 'rgba(148, 163, 184, 0.1)',
    text: '#94a3b8',
    border: 'rgba(148, 163, 184, 0.2)',
    dot: '#94a3b8',
  };

  switch (status) {
    case 'RECEIVED':
    case 'PROCESSING':
    case 'PENDING':
      colorStyle = {
        bg: 'rgba(148, 163, 184, 0.1)',
        text: '#cbd5e1',
        border: 'rgba(148, 163, 184, 0.3)',
        dot: '#94a3b8',
      };
      break;

    case 'CONFIRMED':
      colorStyle = {
        bg: 'rgba(56, 189, 248, 0.1)',
        text: '#38bdf8',
        border: 'rgba(56, 189, 248, 0.3)',
        dot: '#38bdf8',
      };
      break;

    case 'PACKAGING':
    case 'IN_PROGRESS':
      colorStyle = {
        bg: 'rgba(59, 130, 246, 0.15)',
        text: '#60a5fa',
        border: 'rgba(59, 130, 246, 0.35)',
        dot: '#3b82f6',
      };
      break;

    case 'PACKED':
      colorStyle = {
        bg: 'rgba(129, 140, 248, 0.15)',
        text: '#a5b4fc',
        border: 'rgba(129, 140, 248, 0.35)',
        dot: '#818cf8',
      };
      break;

    case 'OUT_FOR_DELIVERY':
      colorStyle = {
        bg: 'rgba(245, 158, 11, 0.15)',
        text: '#fbbf24',
        border: 'rgba(245, 158, 11, 0.35)',
        dot: '#f59e0b',
      };
      break;

    case 'DELIVERED':
    case 'COMPLETED':
      colorStyle = {
        bg: 'rgba(16, 185, 129, 0.15)',
        text: '#34d399',
        border: 'rgba(16, 185, 129, 0.35)',
        dot: '#10b981',
      };
      break;

    case 'NEEDS_REVIEW':
      colorStyle = {
        bg: 'rgba(234, 179, 8, 0.15)',
        text: '#facc15',
        border: 'rgba(234, 179, 8, 0.4)',
        dot: '#eab308',
      };
      break;

    case 'OUT_OF_STOCK':
    case 'FAILED':
    case 'CANCELLED':
      colorStyle = {
        bg: 'rgba(239, 68, 68, 0.15)',
        text: '#f87171',
        border: 'rgba(239, 68, 68, 0.35)',
        dot: '#ef4444',
      };
      break;

    case 'INBOUND':
      colorStyle = {
        bg: 'rgba(56, 189, 248, 0.15)',
        text: '#38bdf8',
        border: 'rgba(56, 189, 248, 0.3)',
        dot: '#38bdf8',
      };
      break;

    case 'OUTBOUND':
      colorStyle = {
        bg: 'rgba(168, 85, 247, 0.15)',
        text: '#c084fc',
        border: 'rgba(168, 85, 247, 0.3)',
        dot: '#a855f7',
      };
      break;
  }

  return (
    <span
      className="badge"
      style={{
        backgroundColor: colorStyle.bg,
        color: colorStyle.text,
        borderColor: colorStyle.border,
      }}
    >
      <span
        className="badge-dot"
        style={{
          backgroundColor: colorStyle.dot,
          boxShadow: `0 0 6px ${colorStyle.dot}`,
        }}
      />
      {label}
    </span>
  );
};
