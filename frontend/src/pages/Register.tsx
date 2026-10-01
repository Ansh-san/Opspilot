import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock, User, Building2, Zap, Eye, EyeOff, AtSign } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Alert } from '@/components/ui/Alert'
import { useAuthStore } from '@/stores/authStore'

export default function Register() {
  const navigate = useNavigate()
  const { register, isLoading, error, clearError } = useAuthStore()

  const [form, setForm] = useState({
    org_name: '',
    org_slug: '',
    full_name: '',
    email: '',
    password: '',
    confirmPassword: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [validationError, setValidationError] = useState('')

  const handleOrgNameChange = (value: string) => {
    const slug = value
      .toLowerCase()
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
    setForm((f) => ({ ...f, org_name: value, org_slug: slug }))
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    clearError()
    setValidationError('')

    if (form.password !== form.confirmPassword) {
      setValidationError('Passwords do not match.')
      return
    }

    try {
      await register({
        org_name: form.org_name,
        org_slug: form.org_slug,
        full_name: form.full_name,
        email: form.email,
        password: form.password,
      })
      navigate('/dashboard')
    } catch {
      // error is set in the store
    }
  }

  const displayError = validationError || error

  return (
    <div className="min-h-screen bg-base flex items-center justify-center p-4">
      {/* Background gradient */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/3 left-1/3 w-[500px] h-[500px] bg-primary-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/3 w-[400px] h-[400px] bg-secondary-500/5 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-lg relative animate-slide-up">
        <div className="glass-card p-8">
          {/* Brand */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-primary-500 to-secondary-500 shadow-glow mb-4">
              <Zap className="w-6 h-6 text-white" strokeWidth={2.5} />
            </div>
            <h1 className="text-2xl font-bold text-slate-100">Create your workspace</h1>
            <p className="text-sm text-slate-500 mt-1">
              Set up OpsPilot for your organization
            </p>
          </div>

          {/* Error */}
          {displayError && (
            <Alert
              variant="error"
              className="mb-6"
              onClose={() => { clearError(); setValidationError('') }}
            >
              {displayError}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {/* Organization section */}
            <div className="pb-4 border-b border-base-border">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                Organization
              </p>
              <div className="space-y-3">
                <Input
                  id="register-org-name"
                  label="Organization name"
                  type="text"
                  placeholder="Acme Corp"
                  value={form.org_name}
                  onChange={(e) => handleOrgNameChange(e.target.value)}
                  leftElement={<Building2 className="w-4 h-4" />}
                  required
                />
                <Input
                  id="register-org-slug"
                  label="Workspace URL"
                  type="text"
                  placeholder="acme-corp"
                  value={form.org_slug}
                  onChange={(e) => setForm((f) => ({ ...f, org_slug: e.target.value }))}
                  leftElement={<AtSign className="w-4 h-4" />}
                  hint="Lowercase letters, numbers, and hyphens only."
                  required
                />
              </div>
            </div>

            {/* User section */}
            <div className="pt-1">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                Admin account
              </p>
              <div className="space-y-3">
                <Input
                  id="register-full-name"
                  label="Full name"
                  type="text"
                  autoComplete="name"
                  placeholder="Jane Smith"
                  value={form.full_name}
                  onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                  leftElement={<User className="w-4 h-4" />}
                  required
                />
                <Input
                  id="register-email"
                  label="Work email"
                  type="email"
                  autoComplete="email"
                  placeholder="jane@acme.com"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  leftElement={<Mail className="w-4 h-4" />}
                  required
                />
                <Input
                  id="register-password"
                  label="Password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Min. 8 chars, 1 uppercase, 1 number"
                  value={form.password}
                  onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                  leftElement={<Lock className="w-4 h-4" />}
                  rightElement={
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="hover:text-slate-300 transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  }
                  hint="At least 8 characters, one uppercase letter, one number."
                  required
                />
                <Input
                  id="register-confirm-password"
                  label="Confirm password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="••••••••"
                  value={form.confirmPassword}
                  onChange={(e) => setForm((f) => ({ ...f, confirmPassword: e.target.value }))}
                  leftElement={<Lock className="w-4 h-4" />}
                  required
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full mt-2"
              isLoading={isLoading}
              size="lg"
            >
              Create workspace
            </Button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            Already have an account?{' '}
            <Link
              to="/login"
              className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
