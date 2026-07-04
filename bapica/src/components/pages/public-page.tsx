import { Navbar } from "@/components/landing/navbar"
import { Footer } from "@/components/landing/footer"

export function PublicPage({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navbar />
      <main className="min-h-screen pt-16">{children}</main>
      <Footer />
    </>
  )
}
