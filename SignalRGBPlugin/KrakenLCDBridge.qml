Item {
  anchors.fill: parent
  Column {
    width: parent.width
    height: parent.height

    Column {
      width: parent.width
      height: 60
      visible: service.controllers.length == 0
      Rectangle {
        width: parent.width
        height: parent.height
        color: "#141414"
        radius: 5
        Column {
          padding: 16
          width: parent.width
          height: parent.height
          spacing: 0
          Text {
            color: theme.primarytextcolor
            text: "Waiting for kraken bridge to start..."
            font.pixelSize: 16
            font.family: "Poppins"
            font.bold: true
          }
        }
      }
    }

    ListView {
      id: controllerList
      model: service.controllers
      width: parent.width - (controllerListScrollBar.width * 1.5)
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
        width: innerContent.width + innerContent.spacing * 2
        height: innerContent.height
        property var device: model.modelData.obj

          Rectangle {
            width: parent.width
            height: parent.height
            color: "#141414"
            radius: 5
          }
          Column {
            id: innerContent
            padding: 16
            spacing: 16

            Row {
              padding: 0

              Text {
                color: theme.primarytextcolor
                text: device.name
                font.pixelSize: 20
                font.family: "Poppins"
                font.bold: true
              }
            }
            Row {
              spacing: 32

              Column {
                Image {
                  height: detailsContent.height
                  width: detailsContent.height
                  source: device.image
                  fillMode: Image.PreserveAspectFit
                  antialiasing: true
                  mipmap:false
                }
              }

              Column {
                id: detailsContent
                spacing: 8

                Text {
                  color: theme.primarytextcolor
                  text: "Status: " + (device.online ? 'Online' : 'Offline')
                }
                Text {
                  color: theme.primarytextcolor
                  text: "Serial: " + device.id
                }
                Text {
                  color: theme.primarytextcolor
                  text: "Resolution: " + device.resolution.width + 'x' + device.resolution.height
                }
                Text {
                  color: theme.primarytextcolor
                  text: "Rendering Mode: " + device.renderingMode
                }
                Text {
                  color: theme.primarytextcolor
                  text: "Rendering Mode: " + device.image
                }
              }
            }
          }
        }
      }
    }
  }