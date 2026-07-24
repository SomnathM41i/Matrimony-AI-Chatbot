import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Crown, Sparkles } from 'lucide-react'
import toast from 'react-hot-toast'
import { createPlanOrder, getPlans, getSubscription } from '../services/commercialService'

const money = (paise) => new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', maximumFractionDigits: 0,
}).format((paise || 0) / 100)

export default function Plans() {
  const queryClient = useQueryClient()
  const { data: plans = [], isLoading } = useQuery({ queryKey: ['commercial-plans'], queryFn: getPlans })
  const { data: subscription } = useQuery({ queryKey: ['commercial-me'], queryFn: getSubscription })
  const order = useMutation({
    mutationFn: createPlanOrder,
    onSuccess: (data) => {
      toast.success(data.message || 'Order created')
      queryClient.invalidateQueries({ queryKey: ['commercial-orders'] })
    },
    onError: (error) => toast.error(error?.response?.data?.detail || 'Could not create order'),
  })

  if (isLoading) return <div className="h-full flex items-center justify-center text-surface-400">Loading plans…</div>

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-surface-100">Membership plans</h1>
          <p className="text-sm text-surface-400 mt-1">Choose a plan with protected AI usage and matrimonial contacts.</p>
        </div>

        {subscription && (
          <div className="card p-4 flex flex-wrap gap-4 items-center justify-between">
            <div>
              <p className="text-sm text-surface-400">Current plan</p>
              <p className="text-lg font-semibold text-primary-300">{subscription.plan_name}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-surface-300">{subscription.credits_remaining.toLocaleString()} AI credits remaining</p>
              <p className="text-xs text-surface-500">Valid until {new Date(subscription.expires_at).toLocaleDateString('en-IN')}</p>
            </div>
          </div>
        )}

        <div className="grid md:grid-cols-3 gap-5">
          {plans.map((plan) => {
            const active = subscription?.plan_code === plan.code
            return (
              <div key={plan.id} className={`card p-6 relative ${active ? 'border-primary-500/60 shadow-glow' : ''}`}>
                {active && <span className="absolute top-3 right-3 text-xs text-primary-300 bg-primary-500/10 px-2 py-1 rounded-full">Current</span>}
                <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center mb-4">
                  {plan.code === 'SILVER' ? <Crown className="w-5 h-5 text-amber-400" /> : <Sparkles className="w-5 h-5 text-primary-400" />}
                </div>
                <h2 className="text-xl font-semibold text-surface-100">{plan.name}</h2>
                <p className="text-3xl font-bold text-white mt-3">{money(plan.price_paise)}</p>
                <p className="text-xs text-surface-500">for {plan.duration_days} days</p>
                <div className="space-y-2 mt-5 text-sm text-surface-300">
                  <p className="flex gap-2"><Check className="w-4 h-4 text-green-400" /> {plan.ai_credits.toLocaleString()} AI credits</p>
                  <p className="flex gap-2"><Check className="w-4 h-4 text-green-400" /> {plan.daily_message_limit} messages/day</p>
                  <p className="flex gap-2"><Check className="w-4 h-4 text-green-400" /> {plan.contact_limit} contacts</p>
                </div>
                <button
                  disabled={active || plan.price_paise === 0 || order.isPending}
                  onClick={() => order.mutate(plan.id)}
                  className="btn-primary w-full mt-6 disabled:opacity-50"
                >
                  {active ? 'Active plan' : plan.price_paise === 0 ? 'Included' : 'Create purchase order'}
                </button>
              </div>
            )
          })}
        </div>
        <p className="text-xs text-surface-500">Payments currently require administrator verification. Live checkout becomes available after a payment gateway is configured.</p>
      </div>
    </div>
  )
}
