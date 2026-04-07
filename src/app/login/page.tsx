'use client'

import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import { Scan } from 'lucide-react'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [message, setMessage] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')

    if (mode === 'login') {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) setError(error.message)
      else window.location.href = '/'
    } else {
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) setError(error.message)
      else setMessage('Check your email for a confirmation link.')
    }
    setLoading(false)
  }
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center mx-auto mb-4">
            <Scan className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">ClearSight Dental</h1>
          <p className="text-slate-500 mt-1">AI-Powered X-Ray Analysis</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900 mb-6">
            {mode === 'login' ? 'Sign in to your account' : 'Create your account'}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 border border-slate-300 rounded-lg text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                placeholder="doctor@practice.com" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 border border-slate-300 rounded-lg text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                placeholder="••••••••" required minLength={6} />
            </div>
            {error && <div className="bg-red-50 text-red-700 text-sm p-3 rounded-lg">{error}</div>}
            {message && <div className="bg-green-50 text-green-700 text-sm p-3 rounded-lg">{message}</div>}            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 transition disabled:opacity-50">
              {loading ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
          <div className="mt-6 text-center text-sm text-slate-500">
            {mode === 'login' ? (
              <>New to ClearSight?{' '}
                <button onClick={() => setMode('signup')} className="text-blue-600 font-medium hover:underline">Create an account</button></>
            ) : (
              <>Already have an account?{' '}
                <button onClick={() => setMode('login')} className="text-blue-600 font-medium hover:underline">Sign in</button></>
            )}
          </div>
        </div>
        <p className="text-center text-xs text-slate-400 mt-6">
          Open Scaffold Labs &bull; Open-source dental AI &bull; Built on DentalGPT + YOLOv8
        </p>
      </div>
    </div>
  )
}