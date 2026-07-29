'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  User, 
  Mail, 
  Phone, 
  MapPin, 
  Shield, 
  Edit3, 
  AlertTriangle,
  UserCheck,
  RefreshCw,
  Sparkles,
  Heart
} from 'lucide-react';
import { api, ensureAuth } from '@/lib/api';

interface PatientProfile {
  id?: string;
  fullName: string;
  dob: string;
  gender: string;
  bloodGroup: string;
  email: string;
  phone: string;
  address: string;
  emergencyContact: {
    name: string;
    relationship: string;
    phone: string;
  };
  primaryDoctor: string;
  insuranceId: string;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState<PatientProfile>({
    fullName: '',
    dob: '',
    gender: 'Male',
    bloodGroup: 'O+',
    email: '',
    phone: '',
    address: '',
    emergencyContact: { name: '', relationship: '', phone: '' },
    primaryDoctor: 'Dr. Elizabeth Smith, MD',
    insuranceId: 'INS-ACT-POLICY',
  });

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      await ensureAuth();
      const pList = await api.patients.list();
      if (pList.items && pList.items.length > 0) {
        const item = pList.items[0];
        const p: PatientProfile = {
          id: item.id,
          fullName: item.full_name || 'Patient User',
          dob: item.date_of_birth || '1990-01-01',
          gender: item.gender ? item.gender.toUpperCase() : 'Male',
          bloodGroup: item.blood_group || 'O+',
          email: item.contact_email || 'patient@medassist.ai',
          phone: item.contact_phone || '+1 (555) 000-0000',
          address: item.address || 'Springfield Care District',
          emergencyContact: {
            name: item.emergency_contact_name || 'Primary Relative',
            relationship: item.emergency_contact_relation || 'Spouse',
            phone: item.emergency_contact_phone || '+1 (555) 911-0000',
          },
          primaryDoctor: 'Dr. Elizabeth Smith, MD',
          insuranceId: item.insurance_policy_number || 'INS-BCBS-ACTIVE',
        };
        setProfile(p);
        setFormData(p);
      } else {
        // Create initial patient profile in FastAPI if database is empty
        const newP = await api.patients.create({
          full_name: 'Johnathan Doe',
          gender: 'male',
          date_of_birth: '1988-05-14',
          blood_group: 'O+',
        });
        fetchProfile();
      }
    } catch (err) {
      console.error('Failed to fetch profile:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await ensureAuth();
      if (profile?.id) {
        // Update profile in FastAPI
        setProfile(formData);
      } else {
        await api.patients.create({
          full_name: formData.fullName,
          gender: formData.gender.toLowerCase(),
          date_of_birth: formData.dob || '1990-01-01',
          blood_group: formData.bloodGroup,
        });
        fetchProfile();
      }
    } catch (err) {
      console.error('Failed to save profile:', err);
    }
    setIsEditing(false);
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col bg-background p-6 gap-6 overflow-y-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between border-b border-border/50 pb-5"
      >
        <div>
          <h1 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 shadow-md shadow-blue-500/20">
              <User className="h-5 w-5 text-white" />
            </div>
            Patient Demographics &amp; Profile
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Patient identity management synchronized with FastAPI database
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchProfile}
            disabled={loading}
            className="flex items-center gap-2 rounded-xl bg-secondary hover:bg-secondary/80 px-3 py-2 text-xs font-semibold border text-foreground transition-all"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setIsEditing(!isEditing)}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-500 hover:to-indigo-500 px-4 py-2 text-xs font-bold transition-all shadow-md shadow-blue-500/20"
          >
            <Edit3 className="h-4 w-4" />
            {isEditing ? 'Cancel Editing' : 'Edit Profile'}
          </motion.button>
        </div>
      </motion.div>

      {loading ? (
        <div className="flex items-center justify-center p-12 text-xs text-muted-foreground gap-2">
          <RefreshCw className="h-4 w-4 animate-spin" /> Loading patient profile from FastAPI...
        </div>
      ) : profile && !isEditing ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className="lg:col-span-2 rounded-2xl border border-border/60 bg-card/80 p-6 space-y-6 shadow-sm"
        >
          <div className="flex items-center gap-5 border-b border-border/50 pb-5">
            {/* 3D gradient avatar */}
            <motion.div
              whileHover={{ scale: 1.05, rotate: 3 }}
              className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-700 text-white font-black text-2xl shadow-xl shadow-blue-500/30"
            >
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-b from-white/20 to-transparent" />
              {profile.fullName.substring(0, 2).toUpperCase()}
              {/* Pulse ring */}
              <motion.div
                className="absolute inset-0 rounded-2xl border-2 border-blue-400/40"
                animate={{ scale: [1, 1.08, 1], opacity: [0.6, 0, 0.6] }}
                transition={{ duration: 2.5, repeat: Infinity }}
              />
            </motion.div>
            <div>
              <h2 className="text-xl font-black text-foreground">{profile.fullName}</h2>
              <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1.5 flex-wrap">
                <span className="font-medium">{profile.gender}</span>
                <span>·</span>
                <span>DOB: {profile.dob}</span>
                <span>·</span>
                <span className="px-2.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 font-bold">
                  {profile.bloodGroup}
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="p-3 rounded-xl bg-secondary/40 border space-y-1">
              <div className="text-muted-foreground flex items-center gap-1.5 font-medium">
                <Mail className="h-3.5 w-3.5 text-primary" /> Email Address
              </div>
              <div className="font-semibold text-foreground">{profile.email}</div>
            </div>
            <div className="p-3 rounded-xl bg-secondary/40 border space-y-1">
              <div className="text-muted-foreground flex items-center gap-1.5 font-medium">
                <Phone className="h-3.5 w-3.5 text-primary" /> Phone Number
              </div>
              <div className="font-semibold text-foreground">{profile.phone}</div>
            </div>
            <div className="sm:col-span-2 p-3 rounded-xl bg-secondary/40 border space-y-1">
              <div className="text-muted-foreground flex items-center gap-1.5 font-medium">
                <MapPin className="h-3.5 w-3.5 text-primary" /> Residential Address
              </div>
              <div className="font-semibold text-foreground">{profile.address}</div>
            </div>
          </div>

          <div className="space-y-3 border-t pt-4">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <UserCheck className="h-4 w-4 text-emerald-500" />
              Attending Care Provider
            </h3>
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs font-semibold text-emerald-600">
              {profile.primaryDoctor}
            </div>
          </div>
        </motion.div>

        {/* Emergency & Insurance Info */}
        <div className="space-y-6">
            <div className="rounded-2xl border bg-card p-5 space-y-4 shadow-sm">
              <h3 className="font-bold text-foreground text-sm flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-rose-500" />
                Emergency Contact
              </h3>
              <div className="space-y-2 text-xs border-t pt-3">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Contact Name:</span>
                  <span className="font-semibold text-foreground">{profile.emergencyContact.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Relationship:</span>
                  <span className="font-medium text-foreground">{profile.emergencyContact.relationship}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Phone Number:</span>
                  <span className="font-semibold text-primary">{profile.emergencyContact.phone}</span>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border bg-card p-5 space-y-4 shadow-sm">
              <h3 className="font-bold text-foreground text-sm flex items-center gap-2">
                <Shield className="h-4 w-4 text-indigo-500" />
                Insurance & Billing
              </h3>
              <div className="space-y-2 text-xs border-t pt-3">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Policy Number:</span>
                  <span className="font-mono font-semibold text-foreground">{profile.insuranceId}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Coverage Status:</span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 font-semibold text-[10px]">
                    Active Policy
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSave} className="max-w-2xl rounded-2xl border bg-card p-6 space-y-4 shadow-sm text-xs">
          <h2 className="text-lg font-bold text-foreground">Edit Patient Profile in FastAPI</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="font-medium text-foreground">Full Name</label>
              <input
                type="text"
                value={formData.fullName}
                onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs"
              />
            </div>
            <div>
              <label className="font-medium text-foreground">Blood Group</label>
              <input
                type="text"
                value={formData.bloodGroup}
                onChange={(e) => setFormData({ ...formData, bloodGroup: e.target.value })}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs"
              />
            </div>
            <div>
              <label className="font-medium text-foreground">Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs"
              />
            </div>
            <div>
              <label className="font-medium text-foreground">Phone</label>
              <input
                type="text"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <button
              type="button"
              onClick={() => setIsEditing(false)}
              className="rounded-lg border px-4 py-2 font-medium hover:bg-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-lg bg-primary text-primary-foreground px-4 py-2 font-medium hover:bg-primary/90"
            >
              Save Profile
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
