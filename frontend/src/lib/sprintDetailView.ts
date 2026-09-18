import type {
  ParticipantReviewDecisionResponse,
  ProjectWorkItem,
  SprintRunDetailResponse,
  SprintRunState,
  SprintSubmissionResponse,
} from './api/types'

export type SprintDetailAction = 'submit' | 'update' | 'resubmit' | null

export type SprintDetailViewModel = {
  sprint: SprintRunDetailResponse
  status: {
    label: string
    tone: 'info' | 'success' | 'warning' | 'danger' | 'muted'
  }
  notice: string
  action: SprintDetailAction
  workItems: ProjectWorkItem[]
  latestSubmission: SprintSubmissionResponse | null
  historicalSubmissions: SprintSubmissionResponse[]
  currentChangesDecision: ParticipantReviewDecisionResponse | null
}

const statePresentation: Record<
  SprintRunState,
  Pick<SprintDetailViewModel, 'status' | 'notice' | 'action'>
> = {
  LOCKED: {
    status: { label: 'قفل‌شده', tone: 'muted' },
    notice:
      'این اسپرینت هنوز باز نشده است. می‌توانید جزئیات آن را مشاهده کنید، اما در حال حاضر امکان ارسال یا انجام عملیات اجرایی روی آن وجود ندارد.',
    action: null,
  },
  ACTIVE: {
    status: { label: 'فعال', tone: 'info' },
    notice:
      'این اسپرینت برای اجرا باز است. هر عضو جاری تیم می‌تواند ارسال را برای تیم ثبت کند؛ سرور وضعیت عضویت، مرحله و مهلت را هنگام ارسال دوباره بررسی می‌کند.',
    action: 'submit',
  },
  SUBMITTED: {
    status: { label: 'ارسال‌شده', tone: 'warning' },
    notice:
      'ارسال فعلی ثبت شده است. تا پیش از شروع بررسی می‌توانید نسخه جدیدتری ثبت کنید؛ ارسال‌های قبلی در سابقه باقی می‌مانند.',
    action: 'update',
  },
  UNDER_REVIEW: {
    status: { label: 'در حال بررسی', tone: 'warning' },
    notice:
      'این اسپرینت در حال بررسی Facilitator است. جزئیات و سابقه ارسال همچنان قابل مشاهده‌اند.',
    action: null,
  },
  CHANGES_REQUESTED: {
    status: { label: 'نیازمند اصلاح', tone: 'danger' },
    notice:
      'برای این اسپرینت اصلاحات درخواست شده است. هر عضو جاری تیم می‌تواند نسخه اصلاح‌شده را برای تیم دوباره ارسال کند.',
    action: 'resubmit',
  },
  COMPLETED: {
    status: { label: 'تکمیل‌شده', tone: 'success' },
    notice:
      'این اسپرینت تکمیل شده است. جزئیات کار و سابقه ارسال فقط برای مشاهده در دسترس‌اند.',
    action: null,
  },
}

export function buildSprintDetailViewModel(
  sprint: SprintRunDetailResponse,
): SprintDetailViewModel {
  const presentation = statePresentation[sprint.state]
  return {
    sprint,
    ...presentation,
    // Preserve the backend's authoritative visibility and ordering.
    workItems: [...sprint.work_items],
    latestSubmission: sprint.latest_submission,
    currentChangesDecision:
      sprint.state === 'CHANGES_REQUESTED' &&
      sprint.latest_submission?.review_decision?.decision === 'CHANGES_REQUESTED'
        ? sprint.latest_submission.review_decision
        : null,
    historicalSubmissions: sprint.latest_submission
      ? sprint.submissions.filter(
          (submission) => submission.id !== sprint.latest_submission?.id,
        )
      : [],
  }
}
