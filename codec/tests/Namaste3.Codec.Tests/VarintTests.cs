// QUOI : VarintTests.cs -- taille/round-trip/débordement du varint base-128, la brique la plus
//   basse du codec.
// POURQUOI : une erreur d'un bit dans le varint déplace toutes les frontières de trame en aval --
//   c'est la classe la plus critique à couvrir en premier.
// COMMENT LANCER : dotnet test --filter VarintTests (depuis codec/).
// GATE : rejouée par gate-codec.sh --epreuve.
using Xunit;

namespace Namaste3.Codec.Tests;

/// <summary>
/// FR : le varint est la brique sous TOUT le reste — framing, tags, longueurs, ids. Une erreur d'un
///      bit ici déplace toutes les frontières de trame.
/// EN : the varint is the brick under EVERYTHING else — framing, tags, lengths, ids. A one-bit
///      error here moves every frame boundary.
/// </summary>
public sealed class VarintTests
{
    [Theory]
    [InlineData(0UL, 1)]
    [InlineData(1UL, 1)]
    [InlineData(127UL, 1)]
    [InlineData(128UL, 2)]
    [InlineData(2306UL, 2)]           // FR : longueur mesurée de la trame `jtg` / measured `jtg` frame length
    [InlineData(16383UL, 2)]
    [InlineData(16384UL, 3)]
    [InlineData(131072UL, 3)]         // FR : plafond client / client cap
    // FR : 4 octets, pas 5 — dans la capture `10 82 8a b8 49` de Jondo, `10` est le TAG du champ 2,
    //      pas un octet du varint. Mesuré ici : 154010882 < 2^28 tient sur 4 octets.
    // EN : 4 bytes, not 5 — in Jondo's `10 82 8a b8 49` capture, `10` is field 2's TAG, not a varint
    //      byte. Measured here: 154010882 < 2^28 fits in 4 bytes.
    [InlineData(154010882UL, 4)]      // FR : mapId cité par Jondo / mapId cited by Jondo
    [InlineData(191105026UL, 4)]      // FR : zaap d'Astrub / Astrub zaap
    [InlineData(ulong.MaxValue, 10)]  // FR : -1 en int32/int64 étendu / -1 sign-extended
    public void Encode_ThenDecode_IsIdentity(ulong value, int expectedSize)
    {
        byte[] encoded = Varint.Encode(value);
        Assert.Equal(expectedSize, encoded.Length);
        Assert.Equal(expectedSize, Varint.Size(value));

        int position = 0;
        Assert.Equal(value, Varint.Read(encoded, ref position));
        Assert.Equal(expectedSize, position);
    }

    /// <summary>
    /// FR : l'id de requête -1 (98,9 % des requêtes mesurées par Jondo) sort sur 10 octets
    ///      `ff ff ff ff ff ff ff ff ff 01` — c'est l'extension de signe protobuf, pas une anomalie.
    /// EN : request id -1 (98.9% of requests measured by Jondo) goes out on 10 bytes — protobuf
    ///      sign extension, not an anomaly.
    /// </summary>
    [Fact]
    public void MinusOne_EncodesAsTenBytes_MatchingJondoCapture()
    {
        byte[] encoded = Varint.Encode(unchecked((ulong)(long)-1));

        Assert.Equal(10, encoded.Length);
        Assert.Equal(
            new byte[] { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x01 },
            encoded);
    }

    /// <summary>
    /// FR : « incomplet » n'est PAS « invalide ». Un varint coupé rend false sans lever : c'est ce
    ///      qui permet au délimiteur d'attendre le segment suivant au lieu de casser la connexion.
    /// EN : "incomplete" is NOT "invalid". A cut varint returns false without throwing: this is what
    ///      lets the delimiter wait for the next segment instead of killing the connection.
    /// </summary>
    [Fact]
    public void TruncatedVarint_ReturnsFalse_WithoutThrowing()
    {
        byte[] cut = { 0x82 };

        Assert.False(Varint.TryRead(cut, 0, out _, out _));
    }

    /// <summary>
    /// FR : tampon vide au point de lecture = incomplet, pas invalide.
    /// EN : empty buffer at read point = incomplete, not invalid.
    /// </summary>
    [Fact]
    public void EmptyBuffer_ReturnsFalse_WithoutThrowing()
    {
        Assert.False(Varint.TryRead(Array.Empty<byte>(), 0, out _, out _));
    }

    /// <summary>
    /// FR : l'écriture est CANONIQUE — la forme la plus courte, toujours la même. C'est ce qui rend
    ///      le ré-encodage reproductible et donc le round-trip signifiant.
    /// EN : writing is CANONICAL — shortest form, always the same. This is what makes re-encoding
    ///      reproducible and therefore the round-trip meaningful.
    /// </summary>
    [Fact]
    public void Encoding_IsCanonical_AcrossFullByteBoundaryRange()
    {
        for (ulong value = 0; value < 40000; value++)
        {
            byte[] encoded = Varint.Encode(value);
            int position = 0;

            Assert.Equal(value, Varint.Read(encoded, ref position));
            Assert.Equal(encoded.Length, position);
            Assert.True(encoded.Length == 1 || encoded[^1] != 0x00,
                $"encodage non canonique pour {value} / non-canonical encoding for {value}");
        }
    }

    /// <summary>
    /// FR : le mode « la longueur se compte elle-même » du client Spin (`SpinHeaderSizeIncludesItself
    ///      = true`, dump `il2cpp.cs:579474`) est implémenté et éprouvé, même s'il n'est pas celui
    ///      des fixtures : ne pas l'écrire aurait laissé un mode déclaré mais jamais exercé.
    /// EN : the client's "length counts itself" mode is implemented and exercised, even though it is
    ///      not the fixtures' mode: leaving it out would have left a declared but never-exercised path.
    /// </summary>
    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(125)]
    [InlineData(126)]
    [InlineData(127)]
    [InlineData(128)]
    [InlineData(16380)]
    [InlineData(70000)]
    public void SelfIncludingHeader_RoundTrips(int payloadSize)
    {
        byte[] payload = new byte[payloadSize];
        for (int i = 0; i < payloadSize; i++)
        {
            payload[i] = (byte)(i & 0x7F);
        }

        byte[] framed = new FrameWriter(headerSizeIncludesItself: true).Frame(payload);

        var reader = new FrameReader(headerSizeIncludesItself: true);
        reader.Append(framed);

        Assert.True(reader.TryReadFrame(out byte[] decoded, out long offset));
        Assert.Equal(0, offset);
        Assert.Equal(payload, decoded);
        reader.AssertDrained();

        // FR : la longueur annoncée inclut bien ses propres octets. EN : declared length includes its own bytes.
        int headerBytes = framed.Length - payloadSize;
        int position = 0;
        Assert.Equal((ulong)framed.Length, Varint.Read(framed, ref position));
        Assert.Equal(headerBytes, position);
    }
}
