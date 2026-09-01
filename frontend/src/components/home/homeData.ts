import roadmapStep01 from '../../assets/home/roadmap-step-01.png'
import roadmapStep02 from '../../assets/home/roadmap-step-02.png'
import roadmapStep03 from '../../assets/home/roadmap-step-03.png'
import roadmapStep04 from '../../assets/home/roadmap-step-04.png'

export const roadmapSteps = [
  {
    image: roadmapStep01,
    title: 'انتخاب نقش و مهارت',
    description: 'نقش و مهارتت را انتخاب کن تا مسیر رشدت مشخص شود.',
  },
  {
    image: roadmapStep02,
    title: 'آمادگی پیش از پروژه',
    description: 'پیش‌نیازها را کامل کن تا برای شروع پروژه آماده شوی.',
  },
  {
    image: roadmapStep03,
    title: 'تشکیل تیم و شروع پروژه',
    description:
      'با تکمیل تیم، پروژه را در فضایی نزدیک به کار واقعی آغاز کن.',
  },
  {
    image: roadmapStep04,
    title: 'تحویل پروژه',
    description:
      'پروژه را Sprint به Sprint پیش ببر و یک خروجی قابل ارائه بساز.',
  },
] as const

export const platformRoles = [
  {
    code: '</>',
    name: 'Backend Developer',
  },
  {
    code: '< />',
    name: 'Frontend Developer',
  },
  {
    code: '◇',
    name: 'Product Designer',
  },
] as const

export const faqItems = [
  {
    question: 'اگر هنوز سابقه کاری ندارم می‌توانم شرکت کنم؟',
    answer:
      'بله. PROLEARN برای توسعه‌دهندگان و طراحان محصول ابتدای مسیر ساخته شده است؛ مهارت‌ها و پیش‌نیازهای هر پروژه پیش از شروع مشخص می‌شوند.',
  },
  {
    question: 'تیم‌های پروژه چند نفره هستند؟',
    answer:
      'هر تیم دقیقاً سه عضو دارد: یک Backend Developer، یک Frontend Developer و یک Product Designer.',
  },
  {
    question: 'پروژه‌ها چطور پیش می‌روند؟',
    answer:
      'هر پروژه به Sprintهای ترتیبی تقسیم می‌شود و خروجی هر Sprint به‌صورت دستی توسط تسهیل‌گر بازبینی می‌شود.',
  },
  {
    question: 'در پایان پروژه چه چیزی می‌سازیم؟',
    answer:
      'هدف، ساخت یک خروجی پروژه‌ای قابل ارائه و تجربه‌ای واقعی از همکاری نقش‌محور در تیم است.',
  },
] as const
