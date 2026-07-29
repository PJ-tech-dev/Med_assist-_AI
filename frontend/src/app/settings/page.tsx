'use client';

import { useState, useEffect } from 'react';
import { 
  Settings, 
  Bot, 
  Bell, 
  ShieldCheck, 
  Server, 
  Key, 
  Check, 
  Save,
  Lock,
  Sparkles,
  Eye,
  EyeOff
} from 'lucide-react';
import { getEmergencyContact, saveEmergencyContact, EmergencyContact } from '@/lib/whatsapp';
import { MessageSquare, Phone } from 'lucide-react';

export default function SettingsPage() {
  const [emergencyAlerts, setEmergencyAlerts] = useState(true);
  const [medReminders, setMedReminders] = useState(true);
  const [saved, setSaved] = useState(false);

  // WhatsApp & Emergency Contact Settings
  const [contact, setContact] = useState<EmergencyContact>({
    name: 'Family Emergency Contact',
    phone: '+919876543210',
    relationship: 'Family / Doctor',
    enableWhatsapp: true,
    highBpmThreshold: 120,
  });

  useEffect(() => {
    setContact(getEmergencyContact());
  }, []);

  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    saveEmergencyContact(contact);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col bg-background p-6 gap-6 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Settings className="h-6 w-6 text-slate-500" />
            System & AI Multi-Agent Configuration
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage your personal emergency contacts, notification preferences, and application settings
          </p>
        </div>
      </div>

      <form onSubmit={handleSaveSettings} className="max-w-3xl space-y-6">
        {/* Notifications */}
        <div className="rounded-2xl border bg-card p-6 space-y-4 shadow-sm">
          <h2 className="text-base font-bold text-foreground flex items-center gap-2">
            <Bell className="h-5 w-5 text-amber-500" />
            Notification & Triage Alert Preferences
          </h2>
          <div className="space-y-3 text-xs">
            <label className="flex items-center justify-between p-3 rounded-xl border bg-secondary/30 cursor-pointer">
              <div>
                <div className="font-semibold text-foreground">Emergency Red-Alert Push Notifications</div>
                <div className="text-muted-foreground text-[11px]">Immediate alerts when red flag triage symptoms are detected</div>
              </div>
              <input
                type="checkbox"
                checked={emergencyAlerts}
                onChange={(e) => setEmergencyAlerts(e.target.checked)}
                className="h-4 w-4 rounded border-primary text-primary focus:ring-primary"
              />
            </label>
            <label className="flex items-center justify-between p-3 rounded-xl border bg-secondary/30 cursor-pointer">
              <div>
                <div className="font-semibold text-foreground">Daily Medication Reminders</div>
                <div className="text-muted-foreground text-[11px]">Dosage reminder alerts for active prescriptions</div>
              </div>
              <input
                type="checkbox"
                checked={medReminders}
                onChange={(e) => setMedReminders(e.target.checked)}
                className="h-4 w-4 rounded border-primary text-primary focus:ring-primary"
              />
            </label>
          </div>
        </div>

        {/* Emergency Contact & Real-Time WhatsApp Alerts */}
        <div className="rounded-2xl border border-emerald-500/30 bg-card p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-foreground flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-emerald-500" />
              Emergency Contact & Real-Time WhatsApp Alert Dispatch
            </h2>
            <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 font-semibold text-[10px] border border-emerald-500/20">
              Live WhatsApp Integration Active
            </span>
          </div>

          <p className="text-xs text-muted-foreground">
            Configure your close contact's phone number. When AI Chat detects a critical cardiac emergency or when your Bluetooth SmartWatch detects high BPM (≥120 bpm), real-time WhatsApp alert messages are automatically dispatched to this contact.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="font-semibold text-foreground">Contact Full Name</label>
              <input
                type="text"
                value={contact.name}
                onChange={(e) => setContact({ ...contact, name: e.target.value })}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                placeholder="e.g. Spouse / Dr. Smith"
              />
            </div>

            <div>
              <label className="font-semibold text-foreground">WhatsApp Emergency Phone Number</label>
              <input
                type="text"
                value={contact.phone}
                onChange={(e) => setContact({ ...contact, phone: e.target.value })}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-primary/40"
                placeholder="e.g. +919876543210 or +1234567890"
              />
            </div>

            <div>
              <label className="font-semibold text-foreground">Relationship / Role</label>
              <input
                type="text"
                value={contact.relationship}
                onChange={(e) => setContact({ ...contact, relationship: e.target.value })}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                placeholder="e.g. Next of Kin / Primary Physician"
              />
            </div>

            <div>
              <label className="font-semibold text-foreground">SmartWatch High BPM Alert Threshold</label>
              <input
                type="number"
                value={contact.highBpmThreshold}
                onChange={(e) => setContact({ ...contact, highBpmThreshold: parseInt(e.target.value) || 120 })}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>
            
            <div className="sm:col-span-2">
              <label className="font-semibold text-foreground">Patient Home Address (For Medical Orders & Delivery)</label>
              <textarea
                value={contact.patientAddress || ''}
                onChange={(e) => setContact({ ...contact, patientAddress: e.target.value })}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none h-16"
                placeholder="Enter your complete home address for medicine deliveries and emergency references"
              />
            </div>
          </div>

          <label className="flex items-center justify-between p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/5 cursor-pointer">
            <div>
              <div className="font-bold text-foreground flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-emerald-500" />
                Enable Real-Time WhatsApp SOS Alerts
              </div>
              <div className="text-muted-foreground text-[11px]">
                Automatically pop up & dispatch WhatsApp alert messages with GPS location when AI detects heart attack or high BPM
              </div>
            </div>
            <input
              type="checkbox"
              checked={contact.enableWhatsapp}
              onChange={(e) => setContact({ ...contact, enableWhatsapp: e.target.checked })}
              className="h-4 w-4 rounded border-emerald-500 text-emerald-600 focus:ring-emerald-500"
            />
          </label>
        </div>

        {/* Save Bar */}
        <div className="flex items-center justify-between pt-2">
          {saved ? (
            <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1.5">
              <Check className="h-4 w-4" /> Emergency Contact & WhatsApp Settings Saved Successfully!
            </span>
          ) : (
            <span />
          )}
          <button
            type="submit"
            className="flex items-center gap-2 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-2.5 text-xs font-semibold shadow-sm transition-all"
          >
            <Save className="h-4 w-4" />
            Save System Settings
          </button>
        </div>
      </form>
    </div>
  );
}
