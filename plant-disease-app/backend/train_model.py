import os
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam

# Paths
DATA_DIR = "data/BugBite"
MODEL_SAVE_PATH = "model/bug_bite_model.h5"
IMG_SIZE = 224
BATCH_SIZE = 32
EPOCHS_FIRST = 10
EPOCHS_FINE = 15

def main():
    if not os.path.exists(DATA_DIR):
        print(f"❌ Dataset not found at {DATA_DIR}")
        print("Expected structure: data/BugBite/<damage_class>/images...")
        print("Damage classes: healthy, notch_damage, shothole_damage, skeletonization,")
        print("                leaf_mining, window_paning, defoliation, leaf_curl_damage, stem_damage")
        return

    # Data generators with augmentation
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=30,
        width_shift_range=0.2,
        height_shift_range=0.2,
        shear_range=0.2,
        zoom_range=0.2,
        horizontal_flip=True,
        validation_split=0.2
    )
    val_datagen = ImageDataGenerator(rescale=1./255, validation_split=0.2)

    train_generator = train_datagen.flow_from_directory(
        DATA_DIR,
        target_size=(IMG_SIZE, IMG_SIZE),
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='training'
    )
    val_generator = val_datagen.flow_from_directory(
        DATA_DIR,
        target_size=(IMG_SIZE, IMG_SIZE),
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='validation'
    )

    num_classes = train_generator.num_classes
    class_names = list(train_generator.class_indices.keys())
    print(f"✅ Found {num_classes} damage classes:")
    for i, name in enumerate(class_names, 1):
        print(f"   {i}. {name}")

    # Load base model
    base_model = MobileNetV2(weights='imagenet', include_top=False, input_shape=(IMG_SIZE, IMG_SIZE, 3))
    base_model.trainable = False

    # Add custom head
    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(128, activation='relu')(x)
    x = Dropout(0.5)(x)
    predictions = Dense(num_classes, activation='softmax')(x)

    model = Model(inputs=base_model.input, outputs=predictions)
    model.compile(optimizer=Adam(learning_rate=0.001), loss='categorical_crossentropy', metrics=['accuracy'])

    # Phase 1: train only head
    print("\n🔹 Phase 1: Training classification head...")
    model.fit(train_generator, validation_data=val_generator, epochs=EPOCHS_FIRST)

    # Phase 2: fine-tune
    print("\n🔹 Phase 2: Fine-tuning...")
    base_model.trainable = True
    for layer in base_model.layers[:100]:
        layer.trainable = False
    model.compile(optimizer=Adam(learning_rate=1e-5), loss='categorical_crossentropy', metrics=['accuracy'])
    model.fit(train_generator, validation_data=val_generator, epochs=EPOCHS_FINE)

    os.makedirs("model", exist_ok=True)
    model.save(MODEL_SAVE_PATH)
    print(f"\n✅ Model saved to {MODEL_SAVE_PATH}")

    # Save class names for backend reference
    with open("model/class_names.txt", "w") as f:
        for name in class_names:
            f.write(name + "\n")
    print(f"✅ Class names saved to model/class_names.txt ({len(class_names)} classes)")

if __name__ == "__main__":
    main()