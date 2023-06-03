export function Name() {
  return 'Kraken LCD Bridge';
}
export function Version() {
  return '0.0.1';
}
export function Type() {
  return 'network';
}
export function Publisher() {
  return 'Brokenmass';
}
export function Documentation() {
  return 'N/A';
}
export function Size() {
  return [6, 6];
}
export function DefaultPosition() {
  return [165, 60];
}
export function DefaultScale() {
  return 1.0;
}
export function DefaultComponentBrand() {
  return 'CompGen';
}
export function LedNames() {
  return [];
}
export function LedPositions() {
  return [];
}

const parameters = {
  screenSize: {
    property: 'screenSize',
    group: '',
    label: 'ScreenSize',
    step: '1',
    type: 'number',
    min: '1',
    max: '80',
    default: '40',
  },
  imageFormat: {
    property: 'imageFormat',
    group: '',
    label: 'Format',
    type: 'combobox',
    values: ['PNG', 'JPEG'],
    default: 'PNG',
  },
  colorPalette: {
    property: 'colorPalette',
    group: '',
    label: 'Color Palette',
    type: 'combobox',
    values: ['WEB', 'ADAPTIVE'],
    default: 'WEB',
  },
  composition: {
    property: 'composition',
    group: '',
    label: 'Composition mode',
    type: 'combobox',
    values: ['OFF', 'OVERLAY', 'MIX'],
    default: 'OVERLAY',
  },
  overlayTransparency: {
    property: 'overlayTransparency',
    group: '',
    label: 'Overlay Transparency',
    step: 1,
    type: 'number',
    min: 0,
    max: 100,
    default: 0,
  },
  spinner: {
    property: 'spinner',
    group: '',
    label: 'Spinner',
    type: 'combobox',
    values: ['OFF', 'STATIC', 'CPU', 'PUMP'],
    default: 'STATIC',
  },
  textOverlay: {
    property: 'textOverlay',
    group: '',
    label: 'Text overlay',
    type: 'boolean',
    default: true,
  },
  titleText: {
    property: 'titleText',
    group: '',
    label: 'titleText',
    type: 'textfield',
    default: 'SignalRGB',
  },
  titleFontSize: {
    property: 'titleFontSize',
    group: '',
    label: 'titleFontSize',
    step: 1,
    type: 'number',
    min: 10,
    max: 200,
    default: 40,
  },
  sensorFontSize: {
    property: 'sensorFontSize',
    group: '',
    label: 'sensorFontSize',
    step: 1,
    type: 'number',
    min: 10,
    max: 320,
    default: 160,
  },
  sensorLabelFontSize: {
    property: 'sensorLabelFontSize',
    group: '',
    label: 'sensorLabelFontSize',
    step: 1,
    type: 'number',
    min: 10,
    max: 200,
    default: 40,
  },
};
export function ControllableParameters() {
  return [
    parameters.screenSize,
    parameters.imageFormat,
    parameters.colorPalette,
    parameters.composition,
  ];
}

/* global
controller:readonly
discovery: readonly
*/

const BRIDGE_ADDRESS = 'http://127.0.0.1:30003';

export function onscreenSizeChanged() {
  device.setSize([screenSize + 1, screenSize + 1]);
}

export function onBrightnessChanged() {
  XmlHttp.Post(
    BRIDGE_ADDRESS + '/brightness',
    () => {},
    {
      brightness: device.getBrightness(),
    },
    false
  );
}

export function oncompositionChanged() {
  if (device.getProperty('composition').value === 'OFF') {
    device.removeProperty('overlayTransparency');
    device.removeProperty('spinner');
    device.removeProperty('textOverlay');
  } else {
    device.addProperty(parameters.overlayTransparency);
    device.addProperty(parameters.spinner);
    device.addProperty(parameters.textOverlay);
  }

  ontextOverlayChanged();
}

export function ontextOverlayChanged() {
  if (device.getProperty('textOverlay')?.value) {
    device.addProperty(parameters.titleText);
    device.addProperty(parameters.titleFontSize);
    device.addProperty(parameters.sensorFontSize);
    device.addProperty(parameters.sensorLabelFontSize);
  } else {
    device.removeProperty('titleText');
    device.removeProperty('titleFontSize');
    device.removeProperty('sensorFontSize');
    device.removeProperty('sensorLabelFontSize');
  }
}

export function Initialize() {
  device.setName(controller.name);
  onscreenSizeChanged();
  oncompositionChanged();
  if (controller.renderingMode === 'RGBA') {
    // RGBA mode does not use a color palette
    device.removeProperty('colorPalette');
  }
  try {
    const image = XmlHttp.downloadImage(device.image);
    device.setImageFromBase64(image);
  } catch (error) {
    device.log('Could not retrieve device image');
  }
  onBrightnessChanged();
}

export function Render() {
  if (!controller.online) {
    return false;
  }

  const RGBData = device.getImageBuffer(0, 0, screenSize, screenSize, {
    flipH: false,
    outputWidth: screenSize,
    outputHeight: screenSize,
    format: imageFormat,
  });

  const data = {
    raw: XmlHttp.Bytes2Base64(RGBData),
    rotation: device.rotation,

    colorPalette: device.getProperty('colorPalette').value,
    composition: device.getProperty('composition').value,
    overlayTransparency: device.getProperty('overlayTransparency')?.value ?? 0,
    spinner: device.getProperty('spinner')?.value ?? false,
    textOverlay: device.getProperty('textOverlay')?.value ?? false,
    titleText: device.getProperty('titleText')?.value,
    titleFontSize: device.getProperty('titleFontSize')?.value,
    sensorFontSize: device.getProperty('sensorFontSize')?.value,
    sensorLabelFontSize: device.getProperty('sensorLabelFontSize')?.value,
  };

  XmlHttp.Post(BRIDGE_ADDRESS + '/frame', () => {}, data, false);
}

export function Shutdown(suspend) {}

export function DiscoveryService() {
  this.IconUrl = `${BRIDGE_ADDRESS}/images/plugin.png`;
  this.Initialize = function () {
    service.log('Initializing Plugin!');
    this.lastUpdate = 0;
  };

  this.ReadInfo = function (xhr) {
    if (xhr.readyState === 4) {
      if (xhr.status === 200 && xhr.responseText) {
        this.deviceInfo = JSON.parse(xhr.responseText);
        if (!this.controller) {
          this.controller = new KrakenLCDBridgeController(this.deviceInfo);
          service.addController(this.controller);
        }
        this.controller.updateStatus({online: true});
      } else if (this.controller) {
        this.controller.updateStatus({online: false});
      }
    }
  };

  this.Update = function () {
    const currentTime = Date.now();
    const self = this;
    if (currentTime - this.lastUpdate >= 2000) {
      this.lastUpdate = currentTime;
      XmlHttp.Get(
        BRIDGE_ADDRESS,
        function (xhr) {
          self.ReadInfo(xhr);
        },
        true
      );
    }
  };

  this.Discovered = function () {};
}

class KrakenLCDBridgeController {
  constructor(info) {
    this.id = info.serial;
    this.name = info.name;
    this.resolution = info.resolution;
    this.renderingMode = info.renderingMode;
    this.image = info.image;
    this.online = true;
    this.lastUpdate = Date.now();
    this.announcedController = false;
  }

  updateStatus({online}) {
    this.online = online;

    this.update();
  }

  update() {
    service.updateController(this);
    if (!this.announcedController) {
      this.announcedController = true;
      service.announceController(this);
    }
  }
}

class XmlHttp {
  static Bytes2Base64(bytes) {
    for (let i = 0; i < bytes.length; i++) {
      if (bytes[i] > 255 || bytes[i] < 0) {
        throw new Error('Invalid bytes');
      }
    }

    const base64Chars =
      'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

    let out = '';

    for (let i = 0; i < bytes.length; i += 3) {
      const groupsOfSix = [undefined, undefined, undefined, undefined];
      groupsOfSix[0] = bytes[i] >> 2;
      groupsOfSix[1] = (bytes[i] & 0x03) << 4;
      if (bytes.length > i + 1) {
        groupsOfSix[1] |= bytes[i + 1] >> 4;
        groupsOfSix[2] = (bytes[i + 1] & 0x0f) << 2;
      }
      if (bytes.length > i + 2) {
        groupsOfSix[2] |= bytes[i + 2] >> 6;
        groupsOfSix[3] = bytes[i + 2] & 0x3f;
      }
      for (let j = 0; j < groupsOfSix.length; j++) {
        if (typeof groupsOfSix[j] === 'undefined') {
          out += '=';
        } else {
          out += base64Chars[groupsOfSix[j]];
        }
      }
    }
    return out;
  }
  static downloadImage(url) {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', controller.image, false);
    xhr.responseType = 'arraybuffer';
    xhr.send(null);

    if (xhr.status === 200) {
      return XmlHttp.Bytes2Base64(new Uint8Array(xhr.response));
    } else {
      throw new Error(`Request error ${xhr.status}`);
    }
  }
  static Get(url, callback, async = true) {
    const xhr = new XMLHttpRequest();
    xhr.timeout = 1000;
    xhr.open('GET', url, async);

    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onreadystatechange = callback.bind(null, xhr);
    xhr.send();
  }

  static Post(url, callback, data, async = true) {
    const xhr = new XMLHttpRequest();
    xhr.timeout = 1000;
    xhr.open('POST', url, async);

    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onreadystatechange = callback.bind(null, xhr);
    xhr.send(JSON.stringify(data));
  }
}
