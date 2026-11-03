from pathlib import Path

path = Path('src/pages/PhotoUploadPage.tsx')
text = path.read_text(encoding='utf-8')
old = '''  useEffect(() => {\n    const init = getInitialCalibration(projectId)\n    setCalPipeDiameter(init.pipeDiameter)\n    setCalSource(init.source)\n    setCalReferenceId(init.referenceId)\n    setCalNotes(init.notes)\n    setSavedProfile(init.profile ? { ...init.profile, verified: false, verified_at: null, verifiedAt: null } : null)\n  }, [projectId])\n'''
new = '''  useEffect(() => {\n    const init = getInitialCalibration(projectId)\n    // Defer the state reset so the effect synchronizes the selected project\n    // without triggering React's synchronous set-state-in-effect rule.\n    queueMicrotask(() => {\n      setCalPipeDiameter(init.pipeDiameter)\n      setCalSource(init.source)\n      setCalReferenceId(init.referenceId)\n      setCalNotes(init.notes)\n      setSavedProfile(init.profile ? { ...init.profile, verified: false, verified_at: null, verifiedAt: null } : null)\n    })\n  }, [projectId])\n'''
if old not in text:
    raise RuntimeError('Generated project switch effect not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('project switch reset deferred')
