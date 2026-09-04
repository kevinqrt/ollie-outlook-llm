/**
 * Event shapes streamed by POST /api/email/suggestion/stream.
 *
 * The backend documents this endpoint's SSE payload as a plain string in
 * openapi.json (FastAPI/hey-api can't express a discriminated union over
 * text/event-stream yet), so these types are kept in sync by hand with
 * backend/app/api/schemas/pipeline_schema.py.
 */

import type { MeetingProposalSchema } from './generated';

export type PlanReadyEvent = {
  type: 'plan_ready';
  steps: string[];
};

export type StepStartedEvent = {
  type: 'step_started';
  index: number;
  label: string;
};

export type StepCompletedEvent = {
  type: 'step_completed';
  index: number;
  label: string;
  result: string;
};

export type DoneEvent = {
  type: 'done';
  finalReply: string;
  meetingProposal?: MeetingProposalSchema | null;
};

export type ErrorEvent = {
  type: 'error';
  detail: string;
};

export type PipelineEvent =
  | PlanReadyEvent
  | StepStartedEvent
  | StepCompletedEvent
  | DoneEvent
  | ErrorEvent;

export function isPipelineEvent(value: unknown): value is PipelineEvent {
  return (
    typeof value === 'object' &&
    value !== null &&
    'type' in value &&
    typeof (value as { type: unknown }).type === 'string'
  );
}
