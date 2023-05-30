Item {
	anchors.fill: parent
	Column {
		width: parent.width
		height: parent.height
		Column {
			width: 450
			height: 115
			Rectangle {
				width: parent.width
				height: parent.height - 10
				color: "#141414"
				radius: 5
				Column {
					x: 10
					y: 10
					width: parent.width - 20
					spacing: 0
					Text {
						color: theme.primarytextcolor
						text: "Discover WLED device by IP"
						font.pixelSize: 16
						font.family: "Poppins"
						font.bold: true
					}
					Row {
						spacing: 6
						Image {
							x: 10
							y: 6
							height: 50
							source: "https://raw.githubusercontent.com/SRGBmods/public/main/images/wled/998_led_nodemcu.png"
							fillMode: Image.PreserveAspectFit
							antialiasing: false
							mipmap: false
						}
						Rectangle {
							x: 10
							y: 6
							width: 200
							height: 50
							radius: 5
							border.color: "#1c1c1c"
							border.width: 2
							color: "#141414"
							TextField {
								width: 180
								leftPadding: 10
								rightPadding: 10
								id: discoverIP
								x: 10
								color: theme.primarytextcolor
								font.family: "Poppins"
								font.bold: true
								font.pixelSize: 20
								verticalAlignment: TextInput.AlignVCenter
								placeholderText: "192.168.0.1:30003"
								onEditingFinished: {
									discovery.forceDiscover(discoverIP.text);
								}
								validator: RegularExpressionValidator {
									regularExpression:  /^((?:[0-1]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])\.){0,3}(?:[0-1]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5]):[0-9]+$/
								}
								background: Item {
									width: parent.width
									height: parent.height
									Rectangle {
										color: "transparent"
										height: 1
										width: parent.width
										anchors.bottom: parent.bottom
									}
								}
							}
						}
					}
				}
				Column {
					x: 260
					y: 4
					width: parent.width - 20
					spacing: 10
					Image {
						x: 10
						y: 10
						height: 50
						source: "https://raw.githubusercontent.com/SRGBmods/public/main/images/wled/wled_logo_akemi.png"
						fillMode: Image.PreserveAspectFit
						antialiasing: false
						mipmap: false
					}
				}
				Column {
					x: 285
					y: 60
					width: parent.width - 20
					spacing: 10
					Item{
						Rectangle {
							width: 120
							height: 26
							color: "#D65A00"
							radius: 5
						}
						width: 120
						height: 26
						ToolButton {
							height: 30
							width: 120
							anchors.verticalCenter: parent.verticalCenter
							font.family: "Poppins"
							font.bold: true
							icon.source: "https://raw.githubusercontent.com/SRGBmods/public/main/images/wled/icon-discover.png"
							text: "Discover"
							anchors.right: parent.right
							onClicked: {
								discovery.forceDiscover(discoverIP.text);
							}
						}
					}
				}
			}
		}

		ListView {
			id: controllerList
			model: service.controllers
			width: contentItem.childrenRect.width + (controllerListScrollBar.width * 1.5)
			height: parent.height - 150
			clip: true

			ScrollBar.vertical: ScrollBar {
				id: controllerListScrollBar
				anchors.right: parent.right
				width: 10
				visible: parent.height < parent.contentHeight
				policy: ScrollBar.AlwaysOn

				height: parent.availableHeight
				contentItem: Rectangle {
					radius: parent.width / 2
					color: theme.scrollBar
				}
			}


			delegate: Item {
				visible: true
				width: 450
				height: 115
				property var device: model.modelData.obj

				Rectangle {
					width: parent.width
					height: parent.height - 10
					color: device.offline ? "#101010" : device.connected ? "#003EFF" : "#292929"
					radius: 5
				}
				Column {
					x: 260
					y: 4
					width: parent.width - 20
					spacing: 10
					Image {
						x: 10
						y: 10
						height: 50
						source: device.offline ? "https://raw.githubusercontent.com/SRGBmods/public/main/images/wled/wled_logo_akemi_mono.png" : device.connected ? "https://raw.githubusercontent.com/SRGBmods/public/main/images/wled/wled_logo_akemi.png" : "https://raw.githubusercontent.com/SRGBmods/public/main/images/wled/wled_logo_akemi_mono.png"
						fillMode: Image.PreserveAspectFit
						antialiasing: false
						mipmap: false
					}
				}
				Column {
					x: 285
					y: 60
					width: parent.width - 20
					spacing: 10
					Item{
            width: 120
						height: 26
						Rectangle {
							width: 120
							height: 26
							color: "#292929"
							MouseArea {
								anchors.fill: parent
								acceptedButtons: Qt.NoButton
								cursorShape: Qt.ForbiddenCursor
							}
						}
						Text {
							anchors.verticalCenter: parent.verticalCenter
							anchors.horizontalCenter: parent.horizontalCenter
							color: theme.primarytextcolor
							font.pixelSize: 15
							font.family: "Poppins"
							font.bold: true
							visible: device.offline
							text: "OFFLINE!"
						}
					}
				}
				Column {
					x: 10
					y: 4
					spacing: 6
					Row {
						width: parent.width - 20
						spacing: 6

						Text {
							color: theme.primarytextcolor
							text: device.address
							font.pixelSize: 16
							font.family: "Poppins"
							font.bold: true
						}
					}
					Row {
						spacing: 6
						Image {
							id: iconDelete
							source: "https://raw.githubusercontent.com/SRGBmods/public/main/images/wled/device-delete.png"
							width: 16; height: 16
							visible: true
							opacity: 1.0
							MouseArea {
								anchors.fill: parent
								hoverEnabled: true
								acceptedButtons: Qt.LeftButton
								onClicked: {
									 device.startDelete();
								}
								onEntered: {
									iconDelete.opacity = 0.8;
								}
								onExited: {
									iconDelete.opacity = 1.0;
								}
							}
						}
					}
					Text {
						color: theme.primarytextcolor
						text: "Address: " + device.address
					}
				}
			}
		}
	}
}