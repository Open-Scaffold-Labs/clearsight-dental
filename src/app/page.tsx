'use client'

import { useState, useCallback } from 'react'
import { Upload, Scan, Shield, Zap, ChevronRight, FileX2 } from 'lucide-react'

type Detection = {
  class: string
  confidence: number
  bbox: [number, number, number, number]
}

type AnalysisResult = {
  image_url: string
  annotated_url: string
  detections: Detection[]
  inference_time_ms: number
}

export default function Home() {
  const [dragOver, setDragOver] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const handleFile = useCallback(async (file: File) => {
    if (!file.type.startsWith('image/')) return
    setPreviewUrl(URL.createObjectURL(file))
    setAnalyzing(true)
    setResult(null)

    const formData = new FormData()
    formData.append('xray', file)

    try {
      const res = await fetch('/api/analyze', { method: 'POST', body: formData })
      const data = await res.json()
      setResult(data)
    } catch (err) {
      console.error('Analysis failed:', err)
    } finally {
      setAnalyzing(false)
    }
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center">
              <Scan className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">ClearSight Dental</h1>
              <p className="text-xs text-slate-500">AI-Powered X-Ray Analysis</p>
            </div>
          </div>
          <nav className="flex items-center gap-6 text-sm text-slate-600">
            <a href="#" className="hover:text-blue-600">Dashboard</a>
            <a href="#" className="hover:text-blue-600">Patients</a>
            <a href="#" className="hover:text-blue-600">History</a>
            <button className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition">
              Upload X-Ray
            </button>
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Conditions Detected', value: '4', icon: Scan, color: 'blue' },
            { label: 'Avg. Inference', value: '<3s', icon: Zap, color: 'amber' },            { label: 'FDA Pathway', value: '510(k)', icon: Shield, color: 'green' },
            { label: 'Monthly Cost', value: '$99', icon: FileX2, color: 'purple' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-3 mb-2">
                <div className={`w-8 h-8 rounded-lg bg-${color}-100 flex items-center justify-center`}>
                  <Icon className={`w-4 h-4 text-${color}-600`} />
                </div>
                <span className="text-2xl font-bold text-slate-900">{value}</span>
              </div>
              <p className="text-sm text-slate-500">{label}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2">
            <div
              onDrop={onDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              className={`rounded-xl border-2 border-dashed p-12 text-center transition-all cursor-pointer ${
                dragOver
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-slate-300 bg-white hover:border-blue-400 hover:bg-blue-50/50'
              }`}
              onClick={() => {
                const input = document.createElement('input')
                input.type = 'file'                input.accept = 'image/*'
                input.onchange = (e) => {
                  const file = (e.target as HTMLInputElement).files?.[0]
                  if (file) handleFile(file)
                }
                input.click()
              }}
            >
              {analyzing ? (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-16 h-16 rounded-full border-4 border-blue-200 border-t-blue-600 animate-spin" />
                  <p className="text-lg font-medium text-slate-700">Analyzing X-Ray...</p>
                  <p className="text-sm text-slate-500">Running YOLOv8 + DentalGPT inference</p>
                </div>
              ) : previewUrl && result ? (
                <div className="space-y-4">
                  <img src={result.annotated_url || previewUrl} alt="Analyzed X-Ray" className="mx-auto max-h-96 rounded-lg" />
                  <div className="flex items-center justify-center gap-2 text-sm text-green-600 font-medium">
                    <Shield className="w-4 h-4" />
                    Analysis complete in {result.inference_time_ms}ms
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center">
                    <Upload className="w-8 h-8 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-lg font-medium text-slate-700">Drop dental X-ray here</p>
                    <p className="text-sm text-slate-500 mt-1">PNG, JPEG, or DICOM — Panoramic, Bitewing, or Periapical</p>                  </div>
                </div>
              )}
            </div>

            {result && result.detections.length > 0 && (
              <div className="mt-6 bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div className="px-5 py-3 bg-slate-50 border-b border-slate-200">
                  <h3 className="font-semibold text-slate-900">Findings ({result.detections.length})</h3>
                </div>
                <div className="divide-y divide-slate-100">
                  {result.detections.map((d, i) => (
                    <div key={i} className="px-5 py-3 flex items-center justify-between hover:bg-slate-50">
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${
                          d.confidence > 0.7 ? 'bg-red-500' : d.confidence > 0.4 ? 'bg-amber-500' : 'bg-yellow-400'
                        }`} />
                        <span className="font-medium text-slate-900">{d.class}</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-sm text-slate-500">
                          Confidence: <span className="font-mono font-medium">{(d.confidence * 100).toFixed(1)}%</span>
                        </span>
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-semibold text-slate-900 mb-4">Detection Capabilities</h3>
              <div className="space-y-3">
                {[
                  { name: 'Caries', desc: 'Early & advanced cavity detection', status: 'active' },
                  { name: 'Deep Caries', desc: 'Advanced decay near pulp', status: 'active' },
                  { name: 'Impacted Teeth', desc: 'Unerupted/misaligned teeth', status: 'active' },
                  { name: 'Periapical Lesion', desc: 'Infection at tooth root', status: 'active' },
                  { name: 'Bone Loss', desc: 'Periodontal bone assessment', status: 'coming' },
                  { name: 'Calculus', desc: 'Tartar buildup detection', status: 'coming' },
                ].map(({ name, desc, status }) => (
                  <div key={name} className="flex items-start gap-3">
                    <div className={`w-2 h-2 mt-2 rounded-full ${status === 'active' ? 'bg-green-500' : 'bg-slate-300'}`} />
                    <div>
                      <p className="text-sm font-medium text-slate-900">{name}</p>
                      <p className="text-xs text-slate-500">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-blue-600 rounded-xl p-5 text-white">
              <h3 className="font-semibold mb-2">Open Source Foundation</h3>
              <p className="text-sm text-blue-100 leading-relaxed">
                Built on DentalGPT (7B) and YOLOv8, fine-tuned with Bay Area dentist consortium data.
                Transparent, auditable, and clinically validated.
              </p>              <a href="https://github.com/FreedomIntelligence/DentalGPT" className="inline-flex items-center gap-1 text-sm font-medium text-white mt-3 hover:underline">
                View model source <ChevronRight className="w-3 h-3" />
              </a>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-semibold text-slate-900 mb-2">Model Info</h3>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Detection</dt>
                  <dd className="font-mono text-slate-900">YOLOv8n</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Reasoning</dt>
                  <dd className="font-mono text-slate-900">DentalGPT-7B</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Inference</dt>
                  <dd className="font-mono text-slate-900">&lt;3 sec</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">FDA Status</dt>
                  <dd className="font-mono text-amber-600">Pre-submission</dd>
                </div>
              </dl>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}