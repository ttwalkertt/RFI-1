(function (root, factory) {
  'use strict';
  const preferences = factory();
  if (typeof module === 'object' && module.exports) module.exports = preferences;
  root.RFIAdminPreferences = preferences;
}(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';

  const NAMESPACE = 'rfi.admin.preferences.v1';
  const keys = Object.freeze({currentFirm: 'current_firm'});

  function storageKey(key) {
    if (typeof key !== 'string' || !key) throw new TypeError('preference key must be a string');
    return `${NAMESPACE}.${key}`;
  }

  function browserStorage() {
    try {
      return typeof localStorage === 'undefined' ? null : localStorage;
    } catch (_error) {
      return null;
    }
  }

  function remove(key, storage = browserStorage()) {
    try {
      if (storage) storage.removeItem(storageKey(key));
      return Boolean(storage);
    } catch (_error) {
      return false;
    }
  }

  function read(key, fallback, validate = function () { return true; }, storage = browserStorage()) {
    let serialized;
    try {
      if (!storage) return fallback;
      serialized = storage.getItem(storageKey(key));
    } catch (_error) {
      return fallback;
    }
    if (serialized === null) return fallback;
    try {
      const value = JSON.parse(serialized);
      if (!validate(value)) {
        remove(key, storage);
        return fallback;
      }
      return value;
    } catch (_error) {
      remove(key, storage);
      return fallback;
    }
  }

  function write(key, value, storage = browserStorage()) {
    try {
      if (!storage) return false;
      const serialized = JSON.stringify(value);
      if (serialized === undefined) return false;
      storage.setItem(storageKey(key), serialized);
      return true;
    } catch (_error) {
      return false;
    }
  }

  function validFirmId(value) {
    return typeof value === 'string' && value.length > 0;
  }

  function rememberedFirm(firms, fallback = '', storage = browserStorage()) {
    const available = new Set(firms.map(firm => firm.firm_id));
    const remembered = read(keys.currentFirm, '', validFirmId, storage);
    if (remembered && available.has(remembered)) return remembered;
    if (remembered) remove(keys.currentFirm, storage);
    return fallback;
  }

  function rememberFirm(firmId) {
    return validFirmId(firmId) ? write(keys.currentFirm, firmId) : remove(keys.currentFirm);
  }

  return Object.freeze({
    namespace: NAMESPACE,
    keys,
    storageKey,
    read,
    write,
    remove,
    rememberedFirm,
    rememberFirm,
  });
}));
