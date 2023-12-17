# iLink Light - Home Assistant Custom Component

## Overview

**iLink Light** is a custom component for Home Assistant that provides seamless integration with iLink-compatible lights. While it is not directly compatible with the iLink app, it serves as a replacement, allowing you to control and automate your iLink-compatible lights through Home Assistant. This custom component offers an enhanced and more flexible experience compared to the original iLink app.

### Affordable Smart Lighting
Those lights are an affordable smart lighting solution that can be easily found on platforms like AliExpress. These budget-friendly lights, when combined with iLink Light for Home Assistant, provide a cost-effective way to enhance your home automation experience.

![lamp](https://github.com/donandren/ilink_light/assets/13854631/ea0759da-33e3-4f00-8370-2b39f340b4d1)
### Original iLink App 

<a href="https://play.google.com/store/apps/details?id=com.jwtian.smartbt&hl=en_US"><img src="https://github.com/donandren/ilink_light/assets/13854631/c66290a5-ef4f-45ea-8c72-e32051df2958" height="48" width="48" ></a>The iLink app, available on the [Google Play Store](https://play.google.com/store/apps/details?id=com.jwtian.smartbt&hl=en_US), is the original application designed for controlling iLink-compatible lights. However, iLink Light surpasses the functionality of the original app by providing a more feature-rich and customizable experience through Home Assistant.

## Features

- **Enhanced Integration with iLight-Compatible Lights:** Control and automate your iLink-compatible lights through Home Assistant, offering a more flexible and powerful smart home experience compared to the original iLink app.

- **Bluetooth Auto-Discovery:** iLink Light supports auto-discovery of iLink-compatible lights via Bluetooth. The component can automatically detect lamps in your vicinity, simplifying the setup process.

- **Manual Addition by MAC Address:** Alternatively, you can manually add iLink-compatible lights by specifying their MAC addresses in the Home Assistant configuration.

- **Smart Lighting Control:** Leverage Home Assistant's powerful automation capabilities to create scenes, schedules, and more, enhancing your lighting experience.

- **Supported Light Features:**
  - **Turn On/Off:** Control the power state of your iLink-compatible lights.
  - **RGB Color:** Adjust the color of your lights using the RGB color model.
  - **Brightness:** Change the brightness level of your lights to set the desired ambiance.
  - **Color Temperature:** Fine-tune the color temperature for a warmer or cooler lighting effect.

## Getting Started

### Prerequisites

- **Home Assistant:** Make sure you have [Home Assistant](https://home-assistant.io) installed and running on your system.

- **HACS:** Install [Home Assistant Community Store](https://hacs.xyz/) to simplify the management of custom components.

- **iLink Light:** Install iLink Light through HACS by adding it to your HACS integrations using the custom repository link: [https://github.com/donandren/ilink_light](https://github.com/donandren/ilink_light).

### Installation

1. Open HACS in the Home Assistant frontend.

2. Navigate to "Integrations" and click on the "+ Explore & Add Repositories" button.

3. Paste the custom repository link [https://github.com/donandren/ilink_light](https://github.com/donandren/ilink_light) into the repository URL field and click "Add."

4. Once added, find "iLink Light" in the list, click on it, and follow the installation instructions.

5. Restart your Home Assistant instance.

## Usage

Once the installation is complete, iLink Light will discover your iLink-compatible lights, either through Bluetooth auto-discovery or by manually adding them with their MAC addresses, and you can start controlling them through Home Assistant.

## Support and Contribution

If you encounter issues or have suggestions for improvement, feel free to [open an issue](https://github.com/donandren/ilink_light/issues). Contributions are welcome!

## Disclaimer

This project is not affiliated with or endorsed by the creators of iLink app or Home Assistant. Use at your own risk.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

