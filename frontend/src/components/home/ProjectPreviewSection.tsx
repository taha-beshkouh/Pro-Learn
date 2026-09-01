import projectPreview01 from '../../assets/home/project-preview-01.png'
import projectPreview02 from '../../assets/home/project-preview-02.png'
import projectPreview03 from '../../assets/home/project-preview-03.png'
import projectPreview04 from '../../assets/home/project-preview-04.png'

const projectPreviewImages = [
  projectPreview01,
  projectPreview02,
  projectPreview03,
  projectPreview04,
] as const

export function ProjectPreviewSection() {
  return (
    <section className="home-projects" aria-labelledby="projects-title">
      <h2 id="projects-title">پیش‌نمایش مسیرهای پروژه</h2>
      <p className="sr-only">
        این تصاویر مرجع بصری صفحه اصلی هستند و به داده زنده پروژه متصل نیستند.
      </p>

      <div className="project-preview-grid">
        {projectPreviewImages.map((image, index) => (
          <figure className="project-preview" key={image}>
            <img src={image} alt={`نمونه بصری پروژه ${index + 1}`} />
          </figure>
        ))}
      </div>
    </section>
  )
}
