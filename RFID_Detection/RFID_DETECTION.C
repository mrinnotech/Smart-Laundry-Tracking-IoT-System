#include <SPI.h>
#include <MFRC522.h>

// --- RC522 pin mapping (NodeMCU) ---
#define SS_PIN   D2   // SDA -> GPIO4
#define RST_PIN  D1   // RST -> GPIO5
// The remaining SPI pins are fixed on ESP8266:
// SCK  = D5 (GPIO14)
// MISO = D6 (GPIO12)
// MOSI = D7 (GPIO13)

MFRC522 mfrc522(SS_PIN, RST_PIN);  // Create instance

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("=====================================");
  Serial.println("   NodeMCU + RC522 RFID Reader");
  Serial.println("=====================================");

  // Initialize SPI bus (no parameters needed on ESP8266)
  SPI.begin();

  // Initialize RC522 module
  mfrc522.PCD_Init();
  Serial.println("Place your RFID card near the reader...");
  Serial.println("-------------------------------------");
}

void loop() {
  // Look for a new card
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    delay(50);
    return;
  }

  // --- Print Card UID ---
  Serial.print("Card UID: ");
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    Serial.print(mfrc522.uid.uidByte[i] < 0x10 ? "0" : "");
    Serial.print(mfrc522.uid.uidByte[i], HEX);
    Serial.print(" ");
  }
  Serial.println();

  // --- Print Card Type ---
  MFRC522::PICC_Type piccType = mfrc522.PICC_GetType(mfrc522.uid.sak);
  Serial.print("Card Type: ");
  Serial.println(mfrc522.PICC_GetTypeName(piccType));

  // --- Halt and stop communication ---
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(1000);
}
