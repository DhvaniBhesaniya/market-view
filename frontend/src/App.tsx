import { lazy, Suspense } from "react"
import { Route, Routes } from "react-router"

import { AppSidebar } from "@/components/app-sidebar"
import { LoadingBlock, Page, PageHeader } from "@/components/page"
import { StatusBar } from "@/components/status-bar"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"

const Overview = lazy(() => import("@/pages/overview"))
const ChartPage = lazy(() => import("@/pages/chart"))
const Strategies = lazy(() => import("@/pages/strategies"))
const StrategyDetail = lazy(() => import("@/pages/strategy-detail"))
const Builder = lazy(() => import("@/pages/builder"))
const Backtests = lazy(() => import("@/pages/backtests"))
const BacktestDetail = lazy(() => import("@/pages/backtest-detail"))
const Validation = lazy(() => import("@/pages/validation"))
const Research = lazy(() => import("@/pages/research"))
const Paper = lazy(() => import("@/pages/paper"))
const Data = lazy(() => import("@/pages/data"))

function NotFound() {
  return (
    <Page>
      <PageHeader title="Page not found" description="Use the sidebar to pick a section." />
    </Page>
  )
}

export function App() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="min-w-0">
        <StatusBar />
        <Suspense fallback={<Page><LoadingBlock height={400} /></Page>}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/chart" element={<ChartPage />} />
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/strategies/:id" element={<StrategyDetail />} />
            <Route path="/builder" element={<Builder />} />
            <Route path="/backtests" element={<Backtests />} />
            <Route path="/backtests/:runId" element={<BacktestDetail />} />
            <Route path="/validation" element={<Validation />} />
            <Route path="/research" element={<Research />} />
            <Route path="/paper" element={<Paper />} />
            <Route path="/data" element={<Data />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </SidebarInset>
    </SidebarProvider>
  )
}

export default App
